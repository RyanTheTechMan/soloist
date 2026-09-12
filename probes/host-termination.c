/* Owned Linux/glibc signal fixture. No account or audio. */
extern void (*signal(int, void (*)(int)))(int);
extern long write(int, const void *, unsigned long);
extern int usleep(unsigned int);
extern int pause(void);

static volatile int received;

static void caught(int number)
{
    received = number;
}

int main(int argc, char **argv)
{
    int number = argc > 1 && argv[1][0] == 'i' ? 2 : 15;
    int default_action = argc > 1 && argv[1][0] == 'd';
    if (!default_action)
        signal(number, caught);
    write(1, "READY\n", 6);
    while (!received) {
        if (default_action)
            pause();
        else
            usleep(10000);
    }
    if (received != number)
        return 1;
    static const char message[] = "PASS: caught host termination in Linux handler\n";
    write(1, message, sizeof(message) - 1);
    return 0;
}
