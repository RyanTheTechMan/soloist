/* Owned Linux/glibc public pthread ABI fixture. No account or audio. */
typedef unsigned long thread_t;
typedef union { long alignment[16]; char storage[128]; } opaque_t;
extern int pthread_create(thread_t *, const void *, void *(*)(void *), void *);
extern int pthread_join(thread_t, void **);
extern int pthread_mutexattr_init(void *);
extern int pthread_mutexattr_destroy(void *);
extern int pthread_mutexattr_setprotocol(void *, int);
extern int pthread_mutexattr_settype(void *, int);
extern int pthread_mutex_init(void *, const void *);
extern int pthread_mutex_destroy(void *);
extern int pthread_mutex_lock(void *);
extern int pthread_mutex_unlock(void *);
extern int usleep(unsigned int);
extern int puts(const char *);
extern int clock_gettime(int, void *);

struct timespec { long seconds, nanoseconds; };
static unsigned raw_word;

static long syscall4(long number, long a, long b, long c, long d)
{
    register long x8 __asm__("x8") = number;
    register long x0 __asm__("x0") = a;
    register long x1 __asm__("x1") = b;
    register long x2 __asm__("x2") = c;
    register long x3 __asm__("x3") = d;
    __asm__ volatile("svc #0" : "+r"(x0) : "r"(x8), "r"(x1), "r"(x2), "r"(x3) : "memory");
    return x0;
}

static long futex(int op, const void *timeout)
{
    return syscall4(98, (long) &raw_word, op | 128, 0, (long) timeout);
}

static void *timed_worker(void *unused)
{
    (void) unused;
    if (futex(7, (void *) 0) != -1 || futex(8, (void *) 0) != -11)
        return (void *) 1; /* EPERM and EAGAIN for another owner's lock. */
    struct timespec deadline;
    if (clock_gettime(0, &deadline))
        return (void *) 2;
    deadline.nanoseconds += 5000000;
    if (deadline.nanoseconds >= 1000000000) {
        deadline.seconds++;
        deadline.nanoseconds -= 1000000000;
    }
    return futex(6, &deadline) == -110 ? (void *) 0 : (void *) 3;
}

static opaque_t mutex;
static unsigned ready, completed;

static void *worker(void *unused)
{
    (void) unused;
    __atomic_fetch_add(&ready, 1, __ATOMIC_SEQ_CST);
    for (int cycle = 0; cycle < 64; cycle++) {
        if (pthread_mutex_lock(&mutex))
            return (void *) 1;
        /* Keep the lock long enough for several contenders to park. */
        usleep(1000);
        completed++;
        if (pthread_mutex_unlock(&mutex))
            return (void *) 2;
    }
    return (void *) 0;
}

int main(void)
{
    if (futex(6, (void *) 0) || futex(6, (void *) 0) != -35)
        return 10; /* EDEADLK on recursive raw LOCK_PI. */
    thread_t timed;
    void *timed_result;
    if (pthread_create(&timed, (void *) 0, timed_worker, (void *) 0) ||
        pthread_join(timed, &timed_result) || timed_result ||
        futex(7, (void *) 0) || raw_word)
        return 11;
    puts("PASS: PI owner checks, trylock, timed waiter removal and unlock");
    opaque_t attr;
    if (pthread_mutexattr_init(&attr) ||
        pthread_mutexattr_setprotocol(&attr, 1) || /* PTHREAD_PRIO_INHERIT */
        pthread_mutexattr_settype(&attr, 1) || /* PTHREAD_MUTEX_RECURSIVE */
        pthread_mutex_init(&mutex, &attr))
        return 1;
    pthread_mutexattr_destroy(&attr);
    if (pthread_mutex_lock(&mutex))
        return 2;
    thread_t threads[3];
    for (int i = 0; i < 3; i++)
        if (pthread_create(&threads[i], (void *) 0, worker, (void *) 0))
            return 3;
    while (__atomic_load_n(&ready, __ATOMIC_SEQ_CST) != 3)
        usleep(1000);
    usleep(20000);
    if (pthread_mutex_unlock(&mutex))
        return 4;
    for (int i = 0; i < 3; i++) {
        void *result;
        if (pthread_join(threads[i], &result) || result)
            return 5;
    }
    if (completed != 192 || pthread_mutex_destroy(&mutex))
        return 6;
    puts("PASS: 192 contended PI mutex acquisitions across three workers");
    return 0;
}
