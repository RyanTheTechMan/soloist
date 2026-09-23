#import <AppKit/AppKit.h>
#import <ServiceManagement/ServiceManagement.h>
#include <string.h>

static NSString *const KeyMask = @"••••••••";

@interface Launcher : NSObject <NSApplicationDelegate, NSTextFieldDelegate>
@property NSWindow *window;
@property NSTextField *engine;
@property NSTextField *key;
@property NSTextField *status;
@property NSTextField *expiry;
@property NSButton *websocket;
@property NSButton *runOnLogin;
@property NSButton *autoStartOnLaunch;
@property NSButton *start;
@property NSButton *stop;
@property NSTask *task;
@property BOOL quitting;
@property BOOL hasSavedKey;
@property BOOL savingKey;
@property BOOL pendingStart;
@property BOOL autoStart;
@property BOOL credentialEdited;
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
    self.window = [[NSWindow alloc] initWithContentRect:NSMakeRect(0, 0, 620, 390)
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
    NSTextField *title = [self label:@"Soloist Runtime" size:24];
    NSView *spacer = [NSView new];
    [spacer setContentHuggingPriority:NSLayoutPriorityDefaultLow forOrientation:NSLayoutConstraintOrientationHorizontal];
    NSButton *download = [NSButton buttonWithTitle:@"Get Soloist" target:self action:@selector(download:)];
    NSStackView *titleRow = [NSStackView stackViewWithViews:@[title, spacer, download]];
    titleRow.spacing = 8;
    [stack addArrangedSubview:titleRow];
    [titleRow.widthAnchor constraintEqualToAnchor:stack.widthAnchor].active = YES;
    self.engine = [NSTextField textFieldWithString:@""];
    self.engine.placeholderString = @"Linux ARM64 Soloist executable";
    self.engine.accessibilityLabel = @"Linux ARM64 Soloist executable";
    NSButton *browse = [NSButton buttonWithTitle:@"Choose…" target:self action:@selector(choose:)];
    NSStackView *engineRow = [NSStackView stackViewWithViews:@[self.engine, browse]];
    engineRow.spacing = 8;
    [stack addArrangedSubview:engineRow];
    [engineRow.widthAnchor constraintEqualToAnchor:stack.widthAnchor].active = YES;
    [browse.widthAnchor constraintEqualToConstant:128].active = YES;
    self.key = [NSTextField textFieldWithString:@""];
    self.key.placeholderString = @"Soloist API key";
    self.key.accessibilityLabel = @"Soloist API key; visible while editing, hidden afterward";
    self.key.toolTip = @"Click to enter or replace the key. A saved key is never revealed.";
    self.key.delegate = self;
    NSButton *getKey = [NSButton buttonWithTitle:@"Get Soloist Key" target:self action:@selector(getKey:)];
    NSStackView *keyRow = [NSStackView stackViewWithViews:@[self.key, getKey]];
    keyRow.spacing = 8;
    [stack addArrangedSubview:keyRow];
    [keyRow.widthAnchor constraintEqualToAnchor:stack.widthAnchor].active = YES;
    [getKey.widthAnchor constraintEqualToConstant:128].active = YES;
    self.status = [self label:@"Choose the official executable and enter your Soloist API key, then Start." size:13];
    [stack addArrangedSubview:self.status];
    [self.status.widthAnchor constraintEqualToAnchor:stack.widthAnchor].active = YES;
    self.expiry = [self label:@"No Soloist build installed yet." size:13];
    [stack addArrangedSubview:self.expiry];
    [self.expiry.widthAnchor constraintEqualToAnchor:stack.widthAnchor].active = YES;
    self.websocket = [NSButton checkboxWithTitle:@"Enable local WebSocket control" target:self action:@selector(websocketChanged:)];
    self.websocket.state = [[NSUserDefaults standardUserDefaults] boolForKey:@"enableWebSocket"]
        ? NSControlStateValueOn : NSControlStateValueOff;
    self.websocket.toolTip = @"Unauthenticated API on this Mac only (127.0.0.1). Never expose it to a LAN or browser.";
    [stack addArrangedSubview:self.websocket];
    self.runOnLogin = [NSButton checkboxWithTitle:@"Run on login" target:self action:@selector(loginChanged:)];
    SMAppServiceStatus loginStatus = SMAppService.mainAppService.status;
    self.runOnLogin.state = (loginStatus == SMAppServiceStatusEnabled ||
                             loginStatus == SMAppServiceStatusRequiresApproval)
        ? NSControlStateValueOn : NSControlStateValueOff;
    [stack addArrangedSubview:self.runOnLogin];
    self.autoStartOnLaunch = [NSButton checkboxWithTitle:@"Auto start on launch" target:self action:@selector(autoStartChanged:)];
    self.autoStartOnLaunch.state = [[NSUserDefaults standardUserDefaults] boolForKey:@"autoStartOnLaunch"]
        ? NSControlStateValueOn : NSControlStateValueOff;
    [stack addArrangedSubview:self.autoStartOnLaunch];
    self.start = [NSButton buttonWithTitle:@"Start" target:self action:@selector(start:)];
    self.stop = [NSButton buttonWithTitle:@"Stop" target:self action:@selector(stop:)];
    self.stop.enabled = NO;
    [stack addArrangedSubview:[NSStackView stackViewWithViews:@[self.start, self.stop]]];
    NSURL *support = [[NSFileManager defaultManager] URLsForDirectory:NSApplicationSupportDirectory inDomains:NSUserDomainMask].firstObject;
    NSURL *config = [support URLByAppendingPathComponent:@"Soloist Runtime/state/installation.json"];
    NSData *data = [NSData dataWithContentsOfURL:config];
    NSDictionary *settings = data ? [NSJSONSerialization JSONObjectWithData:data options:0 error:nil] : nil;
    if ([settings[@"soloist"] isKindOfClass:NSString.class]) self.engine.stringValue = settings[@"soloist"];
    [self refreshExpiry];
    self.autoStart = self.autoStartOnLaunch.state == NSControlStateValueOn && self.engine.stringValue.length > 0;
    if (loginStatus == SMAppServiceStatusRequiresApproval)
        self.status.stringValue = @"Approve Run on login in System Settings → Login Items.";
    [self refreshCredentialStatus];
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
- (void)refreshCredentialStatus {
    NSTask *task = [NSTask new];
    task.executableURL = self.helper;
    task.arguments = @[@"credential", @"status"];
    NSPipe *output = [NSPipe pipe];
    task.standardOutput = output;
    task.standardError = [NSFileHandle fileHandleWithNullDevice];
    task.terminationHandler = ^(NSTask *finished) {
        NSData *data = [output.fileHandleForReading readDataToEndOfFile];
        NSDictionary *reply = data ? [NSJSONSerialization JSONObjectWithData:data options:0 error:nil] : nil;
        dispatch_async(dispatch_get_main_queue(), ^{
            if (self.savingKey || self.credentialEdited) return;
            self.hasSavedKey = finished.terminationStatus == 0 && [reply[@"stored"] boolValue];
            if (!self.key.currentEditor && !self.key.stringValue.length && self.hasSavedKey)
                self.key.stringValue = KeyMask;
            if (self.autoStart && self.hasSavedKey && !self.task) {
                self.autoStart = NO;
                [self start:nil];
            }
        });
    };
    NSError *error = nil;
    if (![task launchAndReturnError:&error])
        self.status.stringValue = @"Could not check macOS Keychain. Enter your API key before starting.";
}
- (void)controlTextDidBeginEditing:(NSNotification *)notification {
    if (notification.object == self.key && [self.key.stringValue isEqualToString:KeyMask])
        self.key.stringValue = @"";
}
- (void)controlTextDidEndEditing:(NSNotification *)notification {
    if (notification.object != self.key) return;
    NSString *value = self.key.stringValue;
    if (!value.length || [value isEqualToString:KeyMask]) {
        if (self.hasSavedKey) self.key.stringValue = KeyMask;
        return;
    }
    [self saveKey:value];
}
- (void)saveKey:(NSString *)value {
    NSData *secret = [value dataUsingEncoding:NSUTF8StringEncoding];
    if (!secret.length || secret.length > 4096 || [value containsString:@"\n"] ||
        [value containsString:@"\r"] || memchr(secret.bytes, 0, secret.length) ||
        ![value isEqualToString:[value stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceCharacterSet]]) {
        self.pendingStart = NO;
        self.status.stringValue = @"The API key must be one nonempty line of at most 4096 bytes.";
        self.key.stringValue = self.hasSavedKey ? KeyMask : @"";
        return;
    }
    self.credentialEdited = YES;
    self.savingKey = YES;
    self.key.stringValue = KeyMask;
    [self.window.undoManager removeAllActions];
    self.status.stringValue = @"Saving API key in macOS Keychain…";
    NSTask *task = [NSTask new];
    task.executableURL = self.helper;
    task.arguments = @[@"credential", @"store"];
    NSPipe *input = [NSPipe pipe];
    NSPipe *errors = [NSPipe pipe];
    task.standardInput = input;
    task.standardOutput = [NSFileHandle fileHandleWithNullDevice];
    task.standardError = errors;
    task.terminationHandler = ^(NSTask *finished) {
        NSData *data = [errors.fileHandleForReading readDataToEndOfFile];
        NSDictionary *diagnostic = data ? [NSJSONSerialization JSONObjectWithData:data options:0 error:nil] : nil;
        dispatch_async(dispatch_get_main_queue(), ^{
            self.savingKey = NO;
            if (finished.terminationStatus == 0) {
                self.hasSavedKey = YES;
                if (self.pendingStart) {
                    self.pendingStart = NO;
                    [self start:nil];
                } else {
                    self.status.stringValue = @"API key saved in macOS Keychain.";
                }
            } else {
                self.pendingStart = NO;
                self.key.stringValue = self.hasSavedKey ? KeyMask : @"";
                self.status.stringValue = [diagnostic[@"message"] isKindOfClass:NSString.class]
                    ? diagnostic[@"message"] : @"Could not save the API key in macOS Keychain.";
            }
            if (self.quitting && !self.task) [NSApp replyToApplicationShouldTerminate:YES];
        });
    };
    NSError *error = nil;
    if (![task launchAndReturnError:&error]) {
        self.savingKey = NO;
        self.pendingStart = NO;
        self.status.stringValue = @"The Keychain helper could not start.";
        return;
    }
    [input.fileHandleForWriting writeData:secret];
    [input.fileHandleForWriting closeFile];
}
- (void)websocketChanged:(id)sender {
    (void)sender;
    [[NSUserDefaults standardUserDefaults] setBool:self.websocket.state == NSControlStateValueOn forKey:@"enableWebSocket"];
    if (self.task) self.status.stringValue = @"WebSocket setting saved; restart the receiver to apply it.";
}
- (void)autoStartChanged:(id)sender {
    (void)sender;
    [[NSUserDefaults standardUserDefaults] setBool:self.autoStartOnLaunch.state == NSControlStateValueOn
                                            forKey:@"autoStartOnLaunch"];
}
- (void)loginChanged:(id)sender {
    (void)sender;
    SMAppService *service = SMAppService.mainAppService;
    NSError *error = nil;
    BOOL enable = self.runOnLogin.state == NSControlStateValueOn;
    BOOL success = enable ? [service registerAndReturnError:&error] : [service unregisterAndReturnError:&error];
    if (!success) {
        self.runOnLogin.state = (service.status == SMAppServiceStatusEnabled ||
                                 service.status == SMAppServiceStatusRequiresApproval)
            ? NSControlStateValueOn : NSControlStateValueOff;
        self.status.stringValue = @"Could not change Run on login. Check System Settings → Login Items.";
        return;
    }
    if (enable && service.status == SMAppServiceStatusRequiresApproval) {
        self.status.stringValue = @"Approve Soloist Runtime in System Settings → Login Items.";
        [SMAppService openSystemSettingsLoginItems];
    }
}
- (void)choose:(NSButton *)sender {
    NSOpenPanel *panel = [NSOpenPanel openPanel];
    panel.canChooseFiles = YES;
    panel.canChooseDirectories = NO;
    panel.allowsMultipleSelection = NO;
    panel.message = @"Select the extracted official Linux ARM64 Soloist executable.";
    [panel beginSheetModalForWindow:self.window completionHandler:^(NSModalResponse result) {
        if (result == NSModalResponseOK) self.engine.stringValue = panel.URL.path;
    }];
}
- (void)download:(id)sender {
    (void)sender;
    [NSWorkspace.sharedWorkspace openURL:[NSURL URLWithString:@"https://developer.spotify.com/documentation/soloist/reference/downloads-and-updates"]];
}
- (void)getKey:(id)sender {
    (void)sender;
    [NSWorkspace.sharedWorkspace openURL:[NSURL URLWithString:@"https://developer.spotify.com/dashboard/soloist"]];
}
- (void)start:(id)sender {
    (void)sender;
    if (self.savingKey) {
        self.pendingStart = YES;
        self.status.stringValue = @"Saving API key before starting…";
        return;
    }
    if (self.key.stringValue.length && ![self.key.stringValue isEqualToString:KeyMask]) {
        self.pendingStart = YES;
        [self saveKey:self.key.stringValue];
        return;
    }
    if (self.task || !self.engine.stringValue.length || !self.hasSavedKey) {
        self.status.stringValue = @"Choose a Soloist executable and enter your API key first.";
        return;
    }
    self.start.enabled = NO;
    self.status.stringValue = @"Checking configuration…";
    NSTask *check = [NSTask new];
    check.executableURL = self.helper;
    check.arguments = @[@"configure", @"--soloist", self.engine.stringValue, @"--keychain"];
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
            if (self.quitting) {
                if (!self.savingKey) [NSApp replyToApplicationShouldTerminate:YES];
                return;
            }
            if (finished.terminationStatus != 0) {
                self.status.stringValue = [diagnostic[@"message"] isKindOfClass:NSString.class] ? diagnostic[@"message"] : @"Setup failed. Check the executable and Keychain access.";
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
                self.status.stringValue = @"Setup is waiting for file access. Check macOS prompts, or Stop and select Soloist with Choose….";
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
            if (self.quitting && !self.savingKey) [NSApp replyToApplicationShouldTerminate:YES];
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
    if (!self.task && !self.savingKey) return NSTerminateNow;
    self.quitting = YES;
    if (self.task) [self stop:nil];
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
