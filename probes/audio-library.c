/* No account state is loaded. Any dlerror output is from these public paths. */
extern void *dlopen(const char *, int);
extern const char *dlerror(void);
extern int puts(const char *);
extern int dlclose(void *);
extern void *dlsym(void *, const char *);
struct sample_spec { int format; unsigned int rate; unsigned char channels; };
int main(void)
{
    void *library = dlopen("libpulse.so.0", 2);
    if (!library) {
        puts(dlerror());
        return 1;
    }
    puts("PASS: Linux PulseAudio client and dependencies loaded");
    const char *(*error_string)(int) = dlsym(library, "pa_strerror");
    void *simple = dlopen("libpulse-simple.so.0", 2);
    if (!simple || !error_string) {
        puts("FAIL: simple audio API not available");
        return 1;
    }
    void *(*create)(const char *, const char *, int, const char *, const char *,
                    const struct sample_spec *, const void *, const void *, int *) =
        dlsym(simple, "pa_simple_new");
    int (*write_audio)(void *, const void *, unsigned long, int *) =
        dlsym(simple, "pa_simple_write");
    void (*free_audio)(void *) = dlsym(simple, "pa_simple_free");
    if (!create || !write_audio || !free_audio)
        return 1;
    struct sample_spec spec = {3, 44100, 2}; /* PA_SAMPLE_S16LE */
    int error = 0;
    void *stream = create(0, "Soloist ABI Probe",
                           1, 0, "silent output test", &spec, 0, 0, &error);
    if (!stream) {
        puts(error_string(error));
        return 1;
    }
    short silence[512] = {0};
    int rc = write_audio(stream, silence, sizeof(silence), &error);
    free_audio(stream);
    dlclose(simple);
    dlclose(library);
    if (rc < 0) {
        puts("FAIL: silent PCM write failed");
        return 1;
    }
    puts("PASS: Linux client connected to native audio and wrote silent PCM");
    return 0;
}
