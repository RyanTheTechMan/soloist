/* Owned fixture using the public libpulse ABI. Writes silence only. */
#include <stddef.h>
typedef struct pa_threaded_mainloop loop_t;
typedef struct pa_mainloop_api api_t;
typedef struct pa_context context_t;
typedef struct pa_stream stream_t;
typedef struct pa_operation operation_t;
struct sample_spec { int format; unsigned int rate; unsigned char channels; };
extern int puts(const char *);
extern loop_t *pa_threaded_mainloop_new(void);
extern api_t *pa_threaded_mainloop_get_api(loop_t *);
extern int pa_threaded_mainloop_start(loop_t *);
extern void pa_threaded_mainloop_stop(loop_t *);
extern void pa_threaded_mainloop_free(loop_t *);
extern void pa_threaded_mainloop_lock(loop_t *);
extern void pa_threaded_mainloop_unlock(loop_t *);
extern void pa_threaded_mainloop_wait(loop_t *);
extern void pa_threaded_mainloop_signal(loop_t *, int);
extern context_t *pa_context_new(api_t *, const char *);
extern int pa_context_connect(context_t *, const char *, int, const void *);
extern int pa_context_get_state(const context_t *);
extern void pa_context_set_state_callback(context_t *, void (*)(context_t *, void *), void *);
extern void pa_context_disconnect(context_t *);
extern void pa_context_unref(context_t *);
extern stream_t *pa_stream_new(context_t *, const char *, const struct sample_spec *, const void *);
extern void pa_stream_set_state_callback(stream_t *, void (*)(stream_t *, void *), void *);
extern int pa_stream_connect_playback(stream_t *, const char *, const void *, int, const void *, stream_t *);
extern int pa_stream_get_state(const stream_t *);
extern operation_t *pa_stream_cork(stream_t *, int, void (*)(stream_t *, int, void *), void *);
extern int pa_stream_write(stream_t *, const void *, size_t, void (*)(void *), long long, int);
extern int pa_stream_disconnect(stream_t *);
extern void pa_stream_unref(stream_t *);
extern void pa_operation_unref(operation_t *);

static void context_changed(context_t *context, void *loop)
{
    (void) context;
    pa_threaded_mainloop_signal(loop, 0);
}
static void stream_changed(stream_t *stream, void *loop)
{
    (void) stream;
    pa_threaded_mainloop_signal(loop, 0);
}
struct completion { loop_t *loop; int done, success; };
static void completed(stream_t *stream, int success, void *userdata)
{
    (void) stream;
    struct completion *completion = userdata;
    completion->done = 1;
    completion->success = success;
    pa_threaded_mainloop_signal(completion->loop, 0);
}
int main(void)
{
    loop_t *loop = pa_threaded_mainloop_new();
    if (!loop || pa_threaded_mainloop_start(loop))
        return 1;
    pa_threaded_mainloop_lock(loop);
    context_t *context = pa_context_new(pa_threaded_mainloop_get_api(loop), "Runtime lifecycle fixture");
    if (!context)
        return 2;
    pa_context_set_state_callback(context, context_changed, loop);
    if (pa_context_connect(context, NULL, 0, NULL))
        return 3;
    while (pa_context_get_state(context) != 4) {
        if (pa_context_get_state(context) >= 5)
            return 4;
        pa_threaded_mainloop_wait(loop);
    }
    puts("PASS: Pulse context ready");
    struct sample_spec spec = {3, 44100, 2};
    stream_t *stream = pa_stream_new(context, "Silent lifecycle test", &spec, NULL);
    if (!stream)
        return 5;
    pa_stream_set_state_callback(stream, stream_changed, loop);
    if (pa_stream_connect_playback(stream, NULL, NULL, 1, NULL, NULL))
        return 6;
    while (pa_stream_get_state(stream) != 2) {
        if (pa_stream_get_state(stream) >= 3)
            return 7;
        pa_threaded_mainloop_wait(loop);
    }
    puts("PASS: Pulse stream ready");
    short silence[882] = {0};
    for (int cycle = 0; cycle < 64; cycle++) {
        struct completion completion = {loop, 0, 0};
        operation_t *op = pa_stream_cork(stream, cycle % 2, completed, &completion);
        if (!op)
            return 8;
        while (!completion.done)
            pa_threaded_mainloop_wait(loop);
        pa_operation_unref(op);
        if (!completion.success || pa_stream_write(stream, silence, sizeof(silence), NULL, 0, 0))
            return 9;
    }
    pa_stream_disconnect(stream);
    pa_stream_unref(stream);
    pa_context_disconnect(context);
    pa_context_unref(context);
    pa_threaded_mainloop_unlock(loop);
    pa_threaded_mainloop_stop(loop);
    pa_threaded_mainloop_free(loop);
    puts("PASS: 64 Pulse cork/uncork callbacks and clean shutdown");
    return 0;
}
