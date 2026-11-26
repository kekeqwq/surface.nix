import AVFoundation
import Foundation
import Darwin
let args = CommandLine.arguments
guard args.count == 3, let seconds = Double(args[2]), seconds.isFinite,
      (3...900).contains(seconds), !FileManager.default.fileExists(atPath: args[1]) else {
    fputs("usage: fullio-mac-capture NEW_PRIVATE_CAF SECONDS (3–900)\n", stderr)
    exit(2)
}
umask(0o077)
let engine = AVAudioEngine()
let input = engine.inputNode
let format = input.outputFormat(forBus: 0)
guard format.channelCount == 1, format.sampleRate > 0 else {
    fputs("select an independent mono microphone as the Mac input\n", stderr)
    exit(2)
}
let file = try AVAudioFile(forWriting: URL(fileURLWithPath: args[1]), settings: format.settings, commonFormat: .pcmFormatFloat32, interleaved: false)
var first: AVAudioFramePosition? = nil
var expected: AVAudioFramePosition = 0
var frames: AVAudioFramePosition = 0
var gaps: AVAudioFramePosition = 0
var peak: Float = 0
var clipped = 0
var firstWall: Double = 0
input.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, stamp in
    guard stamp.isSampleTimeValid, stamp.isHostTimeValid, let channels = buffer.floatChannelData else { return }
    if first == nil {
        first = stamp.sampleTime
        expected = stamp.sampleTime
        firstWall = Date().timeIntervalSince1970 + AVAudioTime.seconds(forHostTime: stamp.hostTime) - AVAudioTime.seconds(forHostTime: mach_absolute_time())
        // Publish the anchor immediately: a later interrupt must not lose it.
        FileHandle.standardOutput.write("firstWall=\(firstWall)\n".data(using: .utf8)!)
        try? "\(firstWall)\n".write(toFile: args[1] + ".firstwall", atomically: true, encoding: .utf8)
    }
    if stamp.sampleTime != expected { gaps += abs(stamp.sampleTime - expected) }
    expected = stamp.sampleTime + AVAudioFramePosition(buffer.frameLength)
    for i in 0..<Int(buffer.frameLength) {
        let a = abs(channels[0][i]); peak = max(peak,a); if a >= 0.99 { clipped += 1 }
    }
    frames += AVAudioFramePosition(buffer.frameLength)
    do { try file.write(from: buffer) } catch { fputs("write failed: \(error)\n",stderr); exit(2) }
}
try engine.start()
print("capture_started rate=\(format.sampleRate) channels=\(format.channelCount)")
fflush(stdout)
RunLoop.current.run(until: Date().addingTimeInterval(seconds))
input.removeTap(onBus: 0)
engine.stop()
print("frames=\(frames) gaps=\(gaps) peak=\(peak) clipped=\(clipped) firstWall=\(firstWall)")
if frames < Int64(seconds * format.sampleRate * 0.8) || peak == 0 || gaps != 0 || clipped != 0 { exit(1) }
