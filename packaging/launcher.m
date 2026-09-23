#import <AppKit/AppKit.h>

@interface Launcher : NSObject <NSApplicationDelegate>
@property NSWindow *window;
@property NSTextField *engine;
@property NSTextField *key;
@property NSTextField *status;
@property NSTextField *expiry;
@property NSButton *websocket;
@property NSButton *start;
@property NSButton *stop;
@property NSTask *task;
@property BOOL quitting;
@end

@implementation Launcher
- (NSURL *)helper {
    return [NSBundle.mainBundle.bundleURL URLByAppendingPathComponent:@"Contents/Helpers/runtime-cli.app/Contents/MacOS/runtime-cli"];
}
- (NSTextField *)label:(NSString *)text size:(CGFloat)size {
    NSTextField *label = [NSTextField wrappingLabelWithString:text];
    label.font = [NSFont systemFontOfSize:size];
    return label;
}
- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    (void)notification;
    NSMenu *menu = [NSMenu new];
    NSMenuItem *application = [NSMenuItem new];
    [menu addItem:application];
    NSMenu *actions = [NSMenu new];
    [actions addItemWithTitle:@"Quit Soloist Runtime" action:@selector(terminate:) keyEquivalent:@"q"];
    application.submenu = actions;
    NSApp.mainMenu = menu;
    self.window = [[NSWindow alloc] initWithContentRect:NSMakeRect(0, 0, 620, 410)
                                            styleMask:NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable
                                              backing:NSBackingStoreBuffered defer:NO];
    self.window.title = @"Soloist Runtime";
    self.window.releasedWhenClosed = NO;
    NSStackView *stack = [NSStackView new];
    stack.orientation = NSUserInterfaceLayoutOrientationVertical;
    stack.alignment = NSLayoutAttributeLeading;
    stack.spacing = 14;
    stack.translatesAutoresizingMaskIntoConstraints = NO;
    [self.window.contentView addSubview:stack];
    [NSLayoutConstraint activateConstraints:@[
        [stack.leadingAnchor constraintEqualToAnchor:self.window.contentView.leadingAnchor constant:24],
        [stack.trailingAnchor constraintEqualToAnchor:self.window.contentView.trailingAnchor constant:-24],
        [stack.topAnchor constraintEqualToAnchor:self.window.contentView.topAnchor constant:24]]];
    [stack addArrangedSubview:[self label:@"Soloist Runtime" size:24]];
    [stack addArrangedSubview:[self label:@"Standalone macOS compatibility backend. No music client required." size:13]];
    self.engine = [NSTextField textFieldWithString:@""];
    self.key = [NSTextField textFieldWithString:@""];
    NSArray *fields = @[self.engine, self.key];
    NSArray *names = @[@"Linux ARM64 Soloist executable", @"API-key file (not the key itself)"];
    for (NSUInteger index = 0; index < fields.count; index++) {
        NSTextField *field = fields[index];
        field.placeholderString = names[index];
        field.accessibilityLabel = names[index];
        NSButton *browse = [NSButton buttonWithTitle:@"Choose…" target:self action:@selector(choose:)];
        browse.tag = (NSInteger)index;
        NSStackView *row = [NSStackView stackViewWithViews:@[field, browse]];
        row.spacing = 8;
        [stack addArrangedSubview:row];
        [row.widthAnchor constraintEqualToAnchor:stack.widthAnchor].active = YES;
        [browse.widthAnchor constraintEqualToConstant:92].active = YES;
    }
    self.status = [self label:@"Choose the official executable and your private API-key file, then Start." size:13];
    [stack addArrangedSubview:self.status];
    [self.status.widthAnchor constraintEqualToAnchor:stack.widthAnchor].active = YES;
    self.expiry = [self label:@"No Soloist build installed yet." size:13];
    [stack addArrangedSubview:self.expiry];
    [self.expiry.widthAnchor constraintEqualToAnchor:stack.widthAnchor].active = YES;
    self.websocket = [NSButton checkboxWithTitle:@"Enable local WebSocket control for trusted apps" target:nil action:nil];
    self.websocket.state = [[NSUserDefaults standardUserDefaults] boolForKey:@"enableWebSocket"]
        ? NSControlStateValueOn : NSControlStateValueOff;
    self.websocket.toolTip = @"Unauthenticated API on this Mac only (127.0.0.1). Never expose it to a LAN or browser.";
    [stack addArrangedSubview:self.websocket];
    NSButton *download = [NSButton buttonWithTitle:@"Get Soloist" target:self action:@selector(download:)];
    self.start = [NSButton buttonWithTitle:@"Start" target:self action:@selector(start:)];
    self.stop = [NSButton buttonWithTitle:@"Stop" target:self action:@selector(stop:)];
    self.stop.enabled = NO;
    [stack addArrangedSubview:[NSStackView stackViewWithViews:@[download, self.start, self.stop]]];
    NSURL *support = [[NSFileManager defaultManager] URLsForDirectory:NSApplicationSupportDirectory inDomains:NSUserDomainMask].firstObject;
    NSURL *config = [support URLByAppendingPathComponent:@"Soloist Runtime/state/installation.json"];
    NSData *data = [NSData dataWithContentsOfURL:config];
    NSDictionary *settings = data ? [NSJSONSerialization JSONObjectWithData:data options:0 error:nil] : nil;
    if ([settings[@"soloist"] isKindOfClass:NSString.class]) self.engine.stringValue = settings[@"soloist"];
    if ([settings[@"api_key_file"] isKindOfClass:NSString.class]) self.key.stringValue = settings[@"api_key_file"];
    [self refreshExpiry];
    [self.window center];
    [self.window makeKeyAndOrderFront:nil];
    [NSApp activate];
}
- (void)refreshExpiry {
    NSURL *support = [[NSFileManager defaultManager] URLsForDirectory:NSApplicationSupportDirectory inDomains:NSUserDomainMask].firstObject;
    NSURL *config = [support URLByAppendingPathComponent:@"Soloist Runtime/state/installation.json"];
    NSData *data = [NSData dataWithContentsOfURL:config];
    NSDictionary *settings = data ? [NSJSONSerialization JSONObjectWithData:data options:0 error:nil] : nil;
    if ([settings[@"soloist"] isKindOfClass:NSString.class]) self.engine.stringValue = settings[@"soloist"];
    NSString *stamp = [settings[@"expected_expiry_at"] isKindOfClass:NSString.class] ? settings[@"expected_expiry_at"] : nil;
    NSString *version = [settings[@"soloist_version"] isKindOfClass:NSString.class] ? settings[@"soloist_version"] : @"unknown";
    NSISO8601DateFormatter *parser = [NSISO8601DateFormatter new];
    NSDate *expiry = stamp ? [parser dateFromString:stamp] : nil;
    if (!expiry) {
        self.expiry.stringValue = settings ? @"Build expiry unknown. Select a current official build to install it." : @"No Soloist build installed yet.";
        return;
    }
    NSDateFormatter *display = [NSDateFormatter new];
    display.dateFormat = @"MMM d, yyyy 'at' HH:mm 'UTC'";
    display.timeZone = [NSTimeZone timeZoneWithAbbreviation:@"UTC"];
    NSString *date = [display stringFromDate:expiry];
    NSTimeInterval remaining = [expiry timeIntervalSinceNow];
    self.expiry.stringValue = remaining <= 0
        ? [NSString stringWithFormat:@"Soloist %@ expired %@. Download a newer build.", version, date]
        : [NSString stringWithFormat:@"Soloist %@ expected expiry: %@ (%ld days left).", version, date, (long)(remaining / 86400)];
}
- (void)choose:(NSButton *)sender {
    NSOpenPanel *panel = [NSOpenPanel openPanel];
    panel.canChooseFiles = YES;
    panel.canChooseDirectories = NO;
    panel.allowsMultipleSelection = NO;
    panel.message = sender.tag == 0 ? @"Select the extracted official Linux ARM64 Soloist executable." : @"Select the owner-only file containing your Soloist API key. Do not select a session file.";
    [panel beginSheetModalForWindow:self.window completionHandler:^(NSModalResponse result) {
        if (result == NSModalResponseOK) {
            NSTextField *field = sender.tag == 0 ? self.engine : self.key;
            field.stringValue = panel.URL.path;
        }
    }];
}
- (void)download:(id)sender {
    (void)sender;
    [NSWorkspace.sharedWorkspace openURL:[NSURL URLWithString:@"https://developer.spotify.com/documentation/soloist/reference/downloads-and-updates"]];
}
- (void)start:(id)sender {
    (void)sender;
    if (self.task || !self.engine.stringValue.length || !self.key.stringValue.length) {
        self.status.stringValue = @"Choose both files first.";
        return;
    }
    self.start.enabled = NO;
    self.status.stringValue = @"Checking configuration…";
    NSTask *check = [NSTask new];
    check.executableURL = self.helper;
    check.arguments = @[@"configure", @"--soloist", self.engine.stringValue, @"--api-key-file", self.key.stringValue];
    NSPipe *errors = [NSPipe pipe];
    NSPipe *output = [NSPipe pipe];
    check.standardOutput = output;
    check.standardError = errors;
    check.terminationHandler = ^(NSTask *finished) {
        NSData *data = [errors.fileHandleForReading readDataToEndOfFile];
        NSData *reply = [output.fileHandleForReading readDataToEndOfFile];
        NSDictionary *diagnostic = data ? [NSJSONSerialization JSONObjectWithData:data options:0 error:nil] : nil;
        NSDictionary *configured = reply ? [NSJSONSerialization JSONObjectWithData:reply options:0 error:nil] : nil;
        dispatch_async(dispatch_get_main_queue(), ^{
            self.task = nil;
            self.stop.enabled = NO;
            if (self.quitting) { [NSApp replyToApplicationShouldTerminate:YES]; return; }
            if (finished.terminationStatus != 0) {
                self.status.stringValue = [diagnostic[@"message"] isKindOfClass:NSString.class] ? diagnostic[@"message"] : @"Setup failed. Check the executable and key-file permissions.";
                self.start.enabled = YES;
                return;
            }
            [self refreshExpiry];
            if ([configured[@"expired"] boolValue]) {
                self.status.stringValue = @"This official Soloist build has expired. Choose a newer download before starting.";
                self.start.enabled = YES;
                return;
            }
            [self launchReceiver];
        });
    };
    NSError *error = nil;
    self.task = check;
    if (![check launchAndReturnError:&error]) {
        self.task = nil;
        self.start.enabled = YES;
        self.status.stringValue = @"The packaged helper could not start.";
    } else {
        self.stop.enabled = YES;
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, 30 * NSEC_PER_SEC), dispatch_get_main_queue(), ^{
            if (self.task == check && check.running) {
                self.status.stringValue = @"Setup is waiting for file access. Check macOS prompts, or Stop and select both files with Choose….";
            }
        });
    }
}
- (void)launchReceiver {
    [[NSUserDefaults standardUserDefaults] setBool:self.websocket.state == NSControlStateValueOn forKey:@"enableWebSocket"];
    NSTask *task = [NSTask new];
    task.executableURL = self.helper;
    task.arguments = @[@"run", @"--audio-latency-ms", @"100", @"--websocket",
                       self.websocket.state == NSControlStateValueOn ? @"on" : @"off"];
    task.standardOutput = [NSFileHandle fileHandleWithNullDevice];
    task.standardError = [NSFileHandle fileHandleWithNullDevice];
    task.terminationHandler = ^(NSTask *finished) {
        dispatch_async(dispatch_get_main_queue(), ^{
            self.task = nil;
            self.start.enabled = YES;
            self.stop.enabled = NO;
            self.status.stringValue = finished.terminationStatus == 0 ? @"Receiver stopped." : @"Receiver stopped after an error. Run the bundled doctor command for diagnostics.";
            if (self.quitting) [NSApp replyToApplicationShouldTerminate:YES];
        });
    };
    NSError *error = nil;
    self.task = task;
    if (![task launchAndReturnError:&error]) {
        self.task = nil;
        self.start.enabled = YES;
        self.status.stringValue = @"The packaged receiver could not start.";
        return;
    }
    self.stop.enabled = YES;
    self.status.stringValue = @"Receiver starting. Select “Soloist Runtime” in Spotify Connect to pair. Closing this app stops it.";
}
- (void)stop:(id)sender {
    (void)sender;
    self.stop.enabled = NO;
    self.status.stringValue = @"Stopping receiver cleanly…";
    if (self.task.running) [self.task terminate];
}
- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication *)sender {
    (void)sender;
    if (!self.task) return NSTerminateNow;
    self.quitting = YES;
    [self stop:nil];
    return NSTerminateLater;
}
- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender {
    (void)sender;
    return YES;
}
@end

int main(void) {
    @autoreleasepool {
        NSApplication *app = NSApplication.sharedApplication;
        [app setActivationPolicy:NSApplicationActivationPolicyRegular];
        __attribute__((objc_precise_lifetime)) Launcher *launcher = [Launcher new];
        app.delegate = launcher;
        [app run];
    }
    return 0;
}
