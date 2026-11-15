// SPDX-License-Identifier: GPL-2.0
/* E11a: one ioctl = one 128-point FFT, two 512-byte Simple DMA transfers.
 * PS cached workspaces -> copy -> coherent bounce buffers -> HP0 -> AXIS.
 * No userspace physical addresses, mmap, SG batching or transfer overlap.
 */
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/of.h>
#include <linux/dmaengine.h>
#include <linux/dma-mapping.h>
#include <linux/completion.h>
#include <linux/miscdevice.h>
#include <linux/fs.h>
#include <linux/io.h>
#include <linux/iopoll.h>
#include <linux/uaccess.h>
#include <linux/mutex.h>
#include <linux/kref.h>
#include <linux/ktime.h>
#include <linux/slab.h>
#include <linux/jiffies.h>
#include "fft128_dma_uapi.h"

#define BYTES 512
#define ID 0x46544480
#define CONTROL 0x04
#define STATUS 0x08
#define CYCLES 0x10
#define IN_COUNT 0x18
#define OUT_COUNT 0x1c
#define IN_STALLS 0x20
#define OUT_STALLS 0x24

struct fft_dma {
    struct miscdevice misc;
    struct mutex lock;
    struct kref refs;
    bool dead, opened;
    void __iomem *regs;
    struct dma_chan *tx, *rx;
    void *txbuf, *rxbuf;
    dma_addr_t txaddr, rxaddr;
    struct completion txdone, rxdone;
    struct fft128_dma_request request; /* allocated once, outside frame timing */
};
static void free_context(struct kref *ref)
{
    kfree(container_of(ref, struct fft_dma, refs));
}
static void completed(void *arg) { complete(arg); }
static void stop_channels(struct fft_dma *f)
{
    /* Synchronize callbacks before freeing/reusing buffers or completions. */
    if (f->tx) dmaengine_terminate_sync(f->tx);
    if (f->rx) dmaengine_terminate_sync(f->rx);
}
static void release_channels(struct fft_dma *f)
{
    stop_channels(f);
    if (f->txbuf) dma_free_coherent(dmaengine_get_dma_device(f->tx), BYTES, f->txbuf, f->txaddr);
    if (f->rxbuf) dma_free_coherent(dmaengine_get_dma_device(f->rx), BYTES, f->rxbuf, f->rxaddr);
    if (f->tx) dma_release_channel(f->tx);
    if (f->rx) dma_release_channel(f->rx);
}
static int fft_open(struct inode *inode, struct file *file)
{
    struct fft_dma *f = container_of(file->private_data, struct fft_dma, misc);
    int ret = 0;
    mutex_lock(&f->lock);
    if (f->dead) ret = -ENODEV;
    else if (f->opened) ret = -EBUSY;
    else { f->opened = true; kref_get(&f->refs); file->private_data = f; }
    mutex_unlock(&f->lock);
    return ret;
}
static int fft_release(struct inode *inode, struct file *file)
{
    struct fft_dma *f = file->private_data;
    mutex_lock(&f->lock);
    f->opened = false;
    mutex_unlock(&f->lock);
    kref_put(&f->refs, free_context);
    return 0;
}
static int wait_until(struct completion *done, unsigned long deadline)
{
    long ret;
    /* Already completed is valid even if userspace was descheduled past deadline. */
    if (try_wait_for_completion(done)) return 0;
    if (time_after_eq(jiffies, deadline)) return -ETIMEDOUT;
    ret = wait_for_completion_interruptible_timeout(done, deadline - jiffies);
    return ret < 0 ? (int)ret : ret == 0 ? -ETIMEDOUT : 0;
}
static long fft_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
    struct fft_dma *f = file->private_data;
    struct fft128_dma_request *r;
    struct dma_async_tx_descriptor *txd, *rxd;
    dma_cookie_t tc, rc;
    unsigned long deadline;
    u32 status;
    bool profile;
    u64 tick = 0;
    int ret;
    if (cmd != FFT128_DMA_RUN) return -ENOTTY;
    ret = mutex_lock_interruptible(&f->lock);
    if (ret) return ret;
    if (f->dead) { ret = -ENODEV; goto unlock; }
    r = &f->request;
    memset(r, 0, sizeof(*r));
    /* Copy only request header first: no profile/timeout decision from unchecked memory. */
    if (copy_from_user(r, (void __user *)arg, offsetof(struct fft128_dma_request, input))) {
        ret = -EFAULT; goto unlock;
    }
    if (r->abi != FFT128_DMA_ABI || (r->flags & ~FFT128_DMA_PROFILE) ||
        r->reserved || !r->timeout_ms || r->timeout_ms > 1000) {
        ret = -EINVAL; goto unlock;
    }
    profile = r->flags & FFT128_DMA_PROFILE;
    if (profile) tick = ktime_get_ns();
    if (copy_from_user(r->input, ((struct fft128_dma_request __user *)arg)->input, BYTES)) {
        ret = -EFAULT; goto unlock;
    }
    memcpy(f->txbuf, r->input, BYTES);
    if (profile) { u64 end = ktime_get_ns(); r->copy_in_ns = end-tick; tick=end; }
    /* Coherent means no dma_sync_* here; ordering is still required. */
    dma_wmb();
    if (readl(f->regs + STATUS) & 1) { ret = -EBUSY; goto unlock; }
    reinit_completion(&f->txdone); reinit_completion(&f->rxdone);
    rxd = dmaengine_prep_slave_single(f->rx, f->rxaddr, BYTES, DMA_DEV_TO_MEM,
                                     DMA_PREP_INTERRUPT | DMA_CTRL_ACK);
    if (!rxd) { ret = -EIO; goto stop; }
    rxd->callback = completed; rxd->callback_param = &f->rxdone;
    rc = dmaengine_submit(rxd);
    if (dma_submit_error(rc)) { ret = rc; goto stop; }
    txd = dmaengine_prep_slave_single(f->tx, f->txaddr, BYTES, DMA_MEM_TO_DEV,
                                     DMA_PREP_INTERRUPT | DMA_CTRL_ACK);
    if (!txd) { ret = -EIO; goto stop; }
    txd->callback = completed; txd->callback_param = &f->txdone;
    tc = dmaengine_submit(txd);
    if (dma_submit_error(tc)) { ret = tc; goto stop; }
    deadline = jiffies + max_t(unsigned long, 1, msecs_to_jiffies(r->timeout_ms));
    /* Arm RX before TX and before starting the FFT to prevent dropped output. */
    dma_async_issue_pending(f->rx);
    dma_async_issue_pending(f->tx);
    writel(1, f->regs + CONTROL);
    if (profile) { u64 end = ktime_get_ns(); r->submit_ns = end-tick; tick=end; }
    ret = wait_until(&f->txdone, deadline);
    if (!ret) ret = wait_until(&f->rxdone, deadline);
    if (ret) goto stop;
    if (profile) { u64 end = ktime_get_ns(); r->wait_ns = end-tick; tick=end; }
    if (dma_async_is_tx_complete(f->tx, tc, NULL, NULL) != DMA_COMPLETE ||
        dma_async_is_tx_complete(f->rx, rc, NULL, NULL) != DMA_COMPLETE) {
        ret = -EIO; goto stop;
    }
    ret = readl_poll_timeout(f->regs + STATUS, status, !(status & 1), 1, 1000);
    if (ret || status != 2 || readl(f->regs + IN_COUNT) != 128 ||
        readl(f->regs + OUT_COUNT) != 128) { ret = -EIO; goto stop; }
    r->status = status;
    if (profile) {
        u64 end;
        r->active_cycles = readl(f->regs + CYCLES);
        r->input_stalls = readl(f->regs + IN_STALLS);
        r->output_stalls = readl(f->regs + OUT_STALLS);
        end = ktime_get_ns(); r->check_ns = end-tick; tick=end;
    }
    dma_rmb();
    memcpy(r->output, f->rxbuf, BYTES);
    if (copy_to_user(((struct fft128_dma_request __user *)arg)->output, r->output, BYTES)) {
        ret = -EFAULT; goto unlock;
    }
    if (profile) r->copy_out_ns = ktime_get_ns()-tick;
    /* The last metadata copy is ioctl tail overhead, included by host wall time. */
    if (copy_to_user(&((struct fft128_dma_request __user *)arg)->active_cycles,
                     &r->active_cycles, sizeof(*r)-offsetof(struct fft128_dma_request, active_cycles)))
        ret = -EFAULT;
    goto unlock;
stop:
    stop_channels(f);
    writel(2, f->regs + CONTROL);
unlock:
    mutex_unlock(&f->lock);
    return ret;
}
static const struct file_operations fft_fops = {
    .owner = THIS_MODULE, .open = fft_open, .release = fft_release,
    .unlocked_ioctl = fft_ioctl, .llseek = no_llseek,
};
static int fft_probe(struct platform_device *pdev)
{
    struct fft_dma *f;
    int ret;
    f = kzalloc(sizeof(*f), GFP_KERNEL);
    if (!f) return -ENOMEM;
    kref_init(&f->refs); mutex_init(&f->lock);
    init_completion(&f->txdone); init_completion(&f->rxdone);
    f->regs = devm_platform_ioremap_resource(pdev, 0);
    if (IS_ERR(f->regs)) { ret=PTR_ERR(f->regs); goto free; }
    if (readl(f->regs) != ID || readl(f->regs+0x0c) != 128 || readl(f->regs+0x14) != FFT128_DMA_ABI) {
        dev_err(&pdev->dev, "wrong FFT DMA frontend/ABI; E11a firmware required\n");
        ret=-ENODEV; goto free;
    }
    f->tx = dma_request_chan(&pdev->dev, "tx");
    if (IS_ERR(f->tx)) { ret=PTR_ERR(f->tx); f->tx=NULL; goto free; }
    f->rx = dma_request_chan(&pdev->dev, "rx");
    if (IS_ERR(f->rx)) { ret=PTR_ERR(f->rx); f->rx=NULL; goto channels; }
    f->txbuf = dma_alloc_coherent(dmaengine_get_dma_device(f->tx), BYTES, &f->txaddr, GFP_KERNEL);
    f->rxbuf = dma_alloc_coherent(dmaengine_get_dma_device(f->rx), BYTES, &f->rxaddr, GFP_KERNEL);
    if (!f->txbuf || !f->rxbuf) { ret=-ENOMEM; goto channels; }
    if (upper_32_bits(f->txaddr) || upper_32_bits(f->rxaddr) || (f->txaddr & 7) || (f->rxaddr & 7)) {
        ret=-EINVAL; goto channels;
    }
    writel(2, f->regs+CONTROL);
    f->misc.minor=MISC_DYNAMIC_MINOR; f->misc.name="fft128-dma";
    f->misc.fops=&fft_fops; f->misc.parent=&pdev->dev; f->misc.mode=0600;
    ret=misc_register(&f->misc);
    if (ret) goto channels;
    platform_set_drvdata(pdev, f);
    dev_info(&pdev->dev, "E11a ready: one FFT/ioctl, coherent bounce buffers, 512B each direction\n");
    return 0;
channels:
    release_channels(f);
free:
    kref_put(&f->refs, free_context);
    return ret;
}
static int fft_remove(struct platform_device *pdev)
{
    struct fft_dma *f = platform_get_drvdata(pdev);
    misc_deregister(&f->misc);
    mutex_lock(&f->lock);
    f->dead=true;
    release_channels(f);
    writel(2, f->regs+CONTROL);
    mutex_unlock(&f->lock);
    kref_put(&f->refs, free_context);
    return 0;
}
static const struct of_device_id fft_match[] = { { .compatible="fmcw,fft128-dma-v1" }, {} };
MODULE_DEVICE_TABLE(of, fft_match);
static struct platform_driver fft_driver = {
    .probe=fft_probe, .remove=fft_remove,
    .driver={ .name="fft128-dma", .of_match_table=fft_match },
};
module_platform_driver(fft_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("FMCW E11a 128-point FFT DMAengine client");
