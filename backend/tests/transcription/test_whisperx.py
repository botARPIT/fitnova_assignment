"""
WhisperX + Pyannote local transcription test
Usage:
    python test_whisperx.py <audio_file> [--hf-token YOUR_TOKEN] [--model small]

Requires: pip install whisperx
GPU: GTX 1650 4GB VRAM → use 'small' or 'base' model
"""

import argparse
import sys
import time
import json
import whisperx
import torch

def main():
    parser = argparse.ArgumentParser(description="WhisperX transcription + diarization test")
    parser.add_argument("audio", help="Path to audio file (wav/mp3/m4a)")
    parser.add_argument("--hf-token", required=True, help="HuggingFace token for pyannote")
    parser.add_argument("--model", default="small", choices=["tiny", "base", "small", "medium"],
                        help="Whisper model size (default: small, fits 4GB VRAM)")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--batch-size", type=int, default=4, help="Batch size (lower = less VRAM)")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    args = parser.parse_args()

    device = args.device
    compute_type = "float16" if device == "cuda" else "int8"

    print(f"═══ WhisperX Test ═══")
    print(f"Device: {device} ({torch.cuda.get_device_name(0) if device == 'cuda' else 'CPU'})")
    print(f"Model: {args.model} | Compute: {compute_type} | Batch: {args.batch_size}")
    print(f"Audio: {args.audio}")
    print()

    # ── Step 1: Transcribe ──────────────────────────────────────
    print("▶ Step 1: Loading Whisper model & transcribing...")
    t0 = time.time()
    model = whisperx.load_model(args.model, device, compute_type=compute_type)
    audio = whisperx.load_audio(args.audio)
    result = model.transcribe(audio, batch_size=args.batch_size)
    t1 = time.time()
    print(f"  ✓ Transcription done in {t1 - t0:.1f}s — {len(result['segments'])} segments")

    # ── Step 2: Align ───────────────────────────────────────────
    print("▶ Step 2: Aligning word-level timestamps...")
    t2 = time.time()
    model_a, metadata = whisperx.load_align_model(
        language_code=result["language"], device=device
    )
    result = whisperx.align(
        result["segments"], model_a, metadata, audio, device,
        return_char_alignments=False
    )
    t3 = time.time()
    print(f"  ✓ Alignment done in {t3 - t2:.1f}s")

    # Free GPU memory before diarization
    del model, model_a
    torch.cuda.empty_cache()

    # ── Step 3: Diarize ─────────────────────────────────────────
    print("▶ Step 3: Running pyannote speaker diarization...")
    t4 = time.time()
    diarize_model = whisperx.DiarizationPipeline(
        use_auth_token=args.hf_token, device=device
    )
    diarize_segments = diarize_model(audio)
    result = whisperx.assign_word_speakers(diarize_segments, result)
    t5 = time.time()
    print(f"  ✓ Diarization done in {t5 - t4:.1f}s")

    # ── Output ──────────────────────────────────────────────────
    print(f"\n{'═' * 60}")
    print(f"TOTAL TIME: {t5 - t0:.1f}s")
    print(f"{'═' * 60}\n")

    lines = []
    for seg in result["segments"]:
        speaker = seg.get("speaker", "UNKNOWN")
        start = seg["start"]
        end = seg["end"]
        text = seg["text"].strip()

        ts = f"{int(start // 60)}:{int(start % 60):02d} – {int(end // 60)}:{int(end % 60):02d}"
        line = f"[{ts}] {speaker}: {text}"
        lines.append(line)
        print(line)

    # Save output
    if args.output:
        with open(args.output, "w") as f:
            f.write("\n".join(lines))
        print(f"\n✓ Saved to {args.output}")

    # Save JSON
    json_out = args.output.replace(".txt", ".json") if args.output else None
    if json_out:
        segments_out = []
        for seg in result["segments"]:
            segments_out.append({
                "speaker": seg.get("speaker", "UNKNOWN"),
                "start": round(seg["start"], 2),
                "end": round(seg["end"], 2),
                "text": seg["text"].strip(),
            })
        with open(json_out, "w") as f:
            json.dump({"segments": segments_out}, f, indent=2)
        print(f"✓ JSON saved to {json_out}")


if __name__ == "__main__":
    main()
