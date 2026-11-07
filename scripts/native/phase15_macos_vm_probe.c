/* Disposable VM-limit diagnostic only. Never linked to C3 or a production worker.
 * All resource changes apply only to this child. No root/entitlements required.
 */
#include <errno.h>
#include <inttypes.h>
#include <mach/mach.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>

int main(int argc, char **argv) {
    if (argc != 2 || (strcmp(argv[1], "absolute") && strcmp(argv[1], "slack"))) return 2;
    struct mach_task_basic_info info;
    mach_msg_type_number_t count = MACH_TASK_BASIC_INFO_COUNT;
    kern_return_t status = task_info(mach_task_self(), MACH_TASK_BASIC_INFO,
                                    (task_info_t)&info, &count);
    if (status != KERN_SUCCESS) return 3;
    struct rlimit before, after;
    if (getrlimit(RLIMIT_AS, &before)) return 4;
    uint64_t limit = strcmp(argv[1], "absolute") == 0 ? 536870912ULL
                    : info.virtual_size + 64ULL*1024*1024;
    struct rlimit request = {limit, limit};
    errno = 0;
    int result = setrlimit(RLIMIT_AS, &request);
    int error = errno;
    if (getrlimit(RLIMIT_AS, &after)) return 5;
    int mapping_ok = 0, mapping_error = 0;
    if (result == 0 && strcmp(argv[1], "slack") == 0) {
        /* Greater than the extra VM allowance; no pages need be committed. */
        void *p = mmap(NULL, 128ULL*1024*1024, PROT_READ|PROT_WRITE,
                       MAP_PRIVATE|MAP_ANON, -1, 0);
        if (p == MAP_FAILED) mapping_error = errno;
        else { mapping_ok = 1; munmap(p, 128ULL*1024*1024); }
    }
    printf("{\"mode\":\"%s\",\"before\":[%llu,%llu],"
           "\"requested\":[%llu,%llu],\"after\":[%llu,%llu],"
           "\"virtual_bytes\":%llu,\"rss_bytes\":%llu,"
           "\"setrlimit_result\":%d,\"errno\":%d,"
           "\"extra_128_mib_mapping_succeeded\":%s,\"mapping_errno\":%d}\n",
           argv[1], (unsigned long long)before.rlim_cur,
           (unsigned long long)before.rlim_max, (unsigned long long)limit,
           (unsigned long long)limit, (unsigned long long)after.rlim_cur,
           (unsigned long long)after.rlim_max, (unsigned long long)info.virtual_size,
           (unsigned long long)info.resident_size, result, error,
           mapping_ok ? "true" : "false", mapping_error);
    return 0;
}
