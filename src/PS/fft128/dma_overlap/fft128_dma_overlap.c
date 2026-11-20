// SPDX-License-Identifier: GPL-2.0
/* E12-4core: one ioctl = 1..128 FFTs on four unchanged arithmetic cores, up to 64 KiB/direction.
 * PS cached workspaces -> copy -> coherent bounce buffers -> HP0 -> AXIS.
 * Per-lane PL ingress/egress FIFOs overlap vectors; host copies and DMA policy unchanged.
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
#include "fft128_dma_overlap_uapi.h"

#define BUFFER_BYTES 65536
#define FFT_COUNT 0x28
#define COMPLETED_FFTS 0x2c
#define CORE_COUNT 0x30
#define CORE0_CYCLES 0x34
#define CORE1_CYCLES 0x38
#define CORE2_CYCLES 0x3c
#define CORE3_CYCLES 0x40
#define ANY_BUSY 0x44
#define MULTI_BUSY 0x48
#define ALL_BUSY 0x4c
#define MULTI_WORK 0x50
#define ALL_WORK 0x54
#define ARBITRATION_STALLS 0x58
#define ID 0x46545085
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
    struct fft128_dma_overlap_request *request; /* allocated once, outside frame timing */
};
static void free_context(struct kref *ref)
{
    struct fft_dma *f = container_of(ref, struct fft_dma, refs);
    kvfree(f->request);
    kfree(f);
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
    if (f->txbuf) dma_free_coherent(dmaengine_get_dma_device(f->tx), BUFFER_BYTES, f->txbuf, f->txaddr);
    if (f->rxbuf) dma_free_coherent(dmaengine_get_dma_device(f->rx), BUFFER_BYTES, f->rxbuf, f->rxaddr);
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
    struct fft128_dma_overlap_request *request;
    struct fft128_dma_overlap_header *r;
    struct fft128_dma_overlap_request __user *user = (void __user *)arg;
    size_t bytes;
    struct dma_async_tx_descriptor *txd, *rxd;
    dma_cookie_t tc, rc;
    unsigned long deadline;
    u32 status;
    bool profile;
    u64 tick = 0;
    int ret;
    if (cmd != FFT128_DMA_OVERLAP_RUN) return -ENOTTY;
    ret = mutex_lock_interruptible(&f->lock);
    if (ret) return ret;
    if (f->dead) { ret = -ENODEV; goto unlock; }
    request = f->request;
    r = &request->meta;
    memset(r, 0, sizeof(*r));
    /* Copy only request header first: no profile/timeout decision from unchecked memory. */
    if (copy_from_user(r, &user->meta, 16)) {
        ret = -EFAULT; goto unlock;
    }
    if (r->abi != FFT128_DMA_OVERLAP_ABI || (r->flags & ~FFT128_DMA_OVERLAP_PROFILE) ||
        !r->fft_count || r->fft_count > 128 || !r->timeout_ms || r->timeout_ms > 1000) {
        ret = -EINVAL; goto unlock;
    }
    bytes = r->fft_count * 512;
    profile = r->flags & FFT128_DMA_OVERLAP_PROFILE;
    if (profile) tick = ktime_get_ns();
    if (copy_from_user(request->input, user->input, bytes)) {
        ret = -EFAULT; goto unlock;
    }
    memcpy(f->txbuf, request->input, bytes);
    if (profile) { u64 end = ktime_get_ns(); r->copy_in_ns = end-tick; tick=end; }
    /* Coherent means no dma_sync_* here; ordering is still required. */
    dma_wmb();
    if (readl(f->regs + STATUS) & 1) { ret = -EBUSY; goto unlock; }
    writel(r->fft_count, f->regs + FFT_COUNT);
    reinit_completion(&f->txdone); reinit_completion(&f->rxdone);
    rxd = dmaengine_prep_slave_single(f->rx, f->rxaddr, bytes, DMA_DEV_TO_MEM,
                                     DMA_PREP_INTERRUPT | DMA_CTRL_ACK);
    if (!rxd) { ret = -EIO; goto stop; }
    rxd->callback = completed; rxd->callback_param = &f->rxdone;
    rc = dmaengine_submit(rxd);
    if (dma_submit_error(rc)) { ret = rc; goto stop; }
    txd = dmaengine_prep_slave_single(f->tx, f->txaddr, bytes, DMA_MEM_TO_DEV,
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
    if (ret || status != 2 || readl(f->regs + IN_COUNT) != bytes/4 ||
        readl(f->regs + OUT_COUNT) != bytes/4 || readl(f->regs + COMPLETED_FFTS) != r->fft_count) { ret = -EIO; goto stop; }
    r->core_count = readl(f->regs + CORE_COUNT);
    if (r->core_count != 4) {
        ret = -EIO; goto stop;
    }
    r->status = status;
    r->input_count = readl(f->regs + IN_COUNT);
    r->output_count = readl(f->regs + OUT_COUNT);
    r->completed_ffts = readl(f->regs + COMPLETED_FFTS);
    if (profile) {
        u64 end;
        r->active_cycles = readl(f->regs + CYCLES);
        r->input_stalls = readl(f->regs + IN_STALLS);
        r->output_stalls = readl(f->regs + OUT_STALLS);
        r->core0_cycles = readl(f->regs + CORE0_CYCLES);
        r->core1_cycles = readl(f->regs + CORE1_CYCLES);
        request->extra.core2_cycles = readl(f->regs + CORE2_CYCLES);
        request->extra.core3_cycles = readl(f->regs + CORE3_CYCLES);
        r->any_busy_cycles = readl(f->regs + ANY_BUSY);
        request->extra.multi_busy_cycles = readl(f->regs + MULTI_BUSY);
        request->extra.all_busy_cycles = readl(f->regs + ALL_BUSY);
        request->extra.multi_work_cycles = readl(f->regs + MULTI_WORK);
        r->all_work_cycles = readl(f->regs + ALL_WORK);
        r->arbitration_stalls = readl(f->regs + ARBITRATION_STALLS);
        request->extra.io_cycles = readl(f->regs + 0x5c);
        request->extra.input_work_cycles = readl(f->regs + 0x60);
        request->extra.output_work_cycles = readl(f->regs + 0x64);
        request->extra.three_cycles = readl(f->regs + 0x68);
        end = ktime_get_ns(); r->check_ns = end-tick; tick=end;
    }
    dma_rmb();
    memcpy(request->output, f->rxbuf, bytes);
    if (copy_to_user(user->output, request->output, bytes)) {
        ret = -EFAULT; goto unlock;
    }
    if (profile) r->copy_out_ns = ktime_get_ns()-tick;
    /* The last metadata copy is ioctl tail overhead, included by host wall time. */
    if (copy_to_user(&user->meta, r, sizeof(*r)) ||
        (profile && copy_to_user(&user->extra, &request->extra, sizeof(request->extra))))
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
    f->request = kvzalloc(sizeof(*f->request), GFP_KERNEL);
    if (!f->request) { ret=-ENOMEM; goto free; }
    init_completion(&f->txdone); init_completion(&f->rxdone);
    f->regs = devm_platform_ioremap_resource(pdev, 0);
    if (IS_ERR(f->regs)) { ret=PTR_ERR(f->regs); goto free; }
    if (readl(f->regs) != ID || readl(f->regs+0x0c) != 128 || readl(f->regs+0x14) != FFT128_DMA_OVERLAP_ABI) {
        dev_err(&pdev->dev, "wrong FFT DMA frontend/ABI; E12-4core firmware required\n");
        ret=-ENODEV; goto free;
    }
    f->tx = dma_request_chan(&pdev->dev, "tx");
    if (IS_ERR(f->tx)) { ret=PTR_ERR(f->tx); f->tx=NULL; goto free; }
    f->rx = dma_request_chan(&pdev->dev, "rx");
    if (IS_ERR(f->rx)) { ret=PTR_ERR(f->rx); f->rx=NULL; goto channels; }
    f->txbuf = dma_alloc_coherent(dmaengine_get_dma_device(f->tx), BUFFER_BYTES, &f->txaddr, GFP_KERNEL);
    f->rxbuf = dma_alloc_coherent(dmaengine_get_dma_device(f->rx), BUFFER_BYTES, &f->rxaddr, GFP_KERNEL);
    if (!f->txbuf || !f->rxbuf) { ret=-ENOMEM; goto channels; }
    if (upper_32_bits(f->txaddr) || upper_32_bits(f->rxaddr) || (f->txaddr & 7) || (f->rxaddr & 7)) {
        ret=-EINVAL; goto channels;
    }
    writel(2, f->regs+CONTROL);
    f->misc.minor=MISC_DYNAMIC_MINOR; f->misc.name="fft128-dma-overlap";
    f->misc.fops=&fft_fops; f->misc.parent=&pdev->dev; f->misc.mode=0600;
    ret=misc_register(&f->misc);
    if (ret) goto channels;
    platform_set_drvdata(pdev, f);
    dev_info(&pdev->dev, "E12-4core ready: up to 128 FFT/ioctl, 4 cores, independent buffered lanes, coherent bounce buffers, 64KiB each direction\n");
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
static const struct of_device_id fft_match[] = { { .compatible="fmcw,fft128-dma-overlap-v5" }, {} };
MODULE_DEVICE_TABLE(of, fft_match);
static struct platform_driver fft_driver = {
    .probe=fft_probe, .remove=fft_remove,
    .driver={ .name="fft128-dma-overlap", .of_match_table=fft_match },
};
module_platform_driver(fft_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("FMCW E12-4core axis-batched 128-point FFT DMAengine client");
