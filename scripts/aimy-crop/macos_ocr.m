#import <Foundation/Foundation.h>
#import <Vision/Vision.h>
#import <ImageIO/ImageIO.h>
#import <CoreServices/CoreServices.h>
#import <math.h>

static void printJSON(id object) {
    NSError *error = nil;
    NSData *data = [NSJSONSerialization dataWithJSONObject:object options:0 error:&error];
    if (!data) {
        fprintf(stderr, "JSON serialization failed: %s\n", error.localizedDescription.UTF8String);
        exit(2);
    }
    fwrite(data.bytes, 1, data.length, stdout);
    fputc('\n', stdout);
}

static NSString *slugFromText(NSString *text) {
    NSMutableString *latin = [text mutableCopy];
    CFStringTransform((__bridge CFMutableStringRef)latin, NULL, kCFStringTransformToLatin, false);
    CFStringTransform((__bridge CFMutableStringRef)latin, NULL, kCFStringTransformStripCombiningMarks, false);
    latin = [[latin lowercaseString] mutableCopy];

    NSRegularExpression *nonAlphaNum = [NSRegularExpression regularExpressionWithPattern:@"[^a-z0-9]+" options:0 error:nil];
    NSString *slug = [nonAlphaNum stringByReplacingMatchesInString:latin options:0 range:NSMakeRange(0, latin.length) withTemplate:@"-"];
    slug = [slug stringByTrimmingCharactersInSet:[NSCharacterSet characterSetWithCharactersInString:@"-"]];
    return slug;
}

int main(int argc, const char * argv[]) {
    @autoreleasepool {
        if (argc >= 3 && strcmp(argv[1], "--slug") == 0) {
            NSString *text = [NSString stringWithUTF8String:argv[2]];
            printJSON(@{ @"slug": slugFromText(text ?: @"") });
            return 0;
        }

        if (argc < 2) {
            fprintf(stderr, "Usage: %s IMAGE_PATH\n", argv[0]);
            return 1;
        }

        NSString *path = [NSString stringWithUTF8String:argv[1]];
        NSURL *url = [NSURL fileURLWithPath:path];

        CGImageSourceRef source = CGImageSourceCreateWithURL((__bridge CFURLRef)url, NULL);
        if (!source) {
            fprintf(stderr, "Could not open image: %s\n", argv[1]);
            return 2;
        }

        CFDictionaryRef propertiesRef = CGImageSourceCopyPropertiesAtIndex(source, 0, NULL);
        CFRelease(source);
        if (!propertiesRef) {
            fprintf(stderr, "Could not read image properties: %s\n", argv[1]);
            return 2;
        }

        NSDictionary *properties = CFBridgingRelease(propertiesRef);
        NSNumber *widthValue = properties[(NSString *)kCGImagePropertyPixelWidth];
        NSNumber *heightValue = properties[(NSString *)kCGImagePropertyPixelHeight];
        const size_t width = widthValue.unsignedLongLongValue;
        const size_t height = heightValue.unsignedLongLongValue;
        if (width == 0 || height == 0) {
            fprintf(stderr, "Could not determine image size: %s\n", argv[1]);
            return 2;
        }

        VNRecognizeTextRequest *request = [[VNRecognizeTextRequest alloc] init];
        request.recognitionLevel = VNRequestTextRecognitionLevelAccurate;
        request.usesLanguageCorrection = YES;
        request.recognitionLanguages = @[ @"ja-JP", @"en-US" ];
        request.minimumTextHeight = 0.006;

        VNImageRequestHandler *handler = [[VNImageRequestHandler alloc] initWithURL:url options:@{}];
        NSError *error = nil;
        BOOL ok = [handler performRequests:@[request] error:&error];
        if (!ok) {
            fprintf(stderr, "Vision OCR failed: %s\n", error.localizedDescription.UTF8String);
            return 3;
        }

        NSMutableArray *lines = [NSMutableArray array];
        for (VNRecognizedTextObservation *observation in request.results) {
            VNRecognizedText *candidate = [[observation topCandidates:1] firstObject];
            if (!candidate || candidate.string.length == 0) {
                continue;
            }

            CGRect b = observation.boundingBox;
            const double left = b.origin.x * width;
            const double top = (1.0 - b.origin.y - b.size.height) * height;
            const double right = (b.origin.x + b.size.width) * width;
            const double bottom = (1.0 - b.origin.y) * height;

            [lines addObject:@{
                @"text": candidate.string,
                @"confidence": @(candidate.confidence),
                @"box": @[ @(left), @(top), @(right), @(bottom) ]
            }];
        }

        [lines sortUsingComparator:^NSComparisonResult(NSDictionary *a, NSDictionary *b) {
            double ay = [a[@"box"][1] doubleValue];
            double by = [b[@"box"][1] doubleValue];
            if (fabs(ay - by) > 8.0) {
                return ay < by ? NSOrderedAscending : NSOrderedDescending;
            }
            double ax = [a[@"box"][0] doubleValue];
            double bx = [b[@"box"][0] doubleValue];
            if (ax == bx) return NSOrderedSame;
            return ax < bx ? NSOrderedAscending : NSOrderedDescending;
        }];

        printJSON(@{
            @"width": @(width),
            @"height": @(height),
            @"lines": lines
        });
    }
    return 0;
}
