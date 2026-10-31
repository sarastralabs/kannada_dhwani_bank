"""One-shot Parler quality check (run with .venv-parler python)."""
import torch
import soundfile as sf
from parler_model_utils import dtype_label, load_parler_model
from transformers import AutoTokenizer

device = "cuda:0" if torch.cuda.is_available() else "cpu"
print("device", device)
model, dtype = load_parler_model("ai4bharat/indic-parler-tts", device)
print("dtype", dtype_label(dtype))
tok = AutoTokenizer.from_pretrained("ai4bharat/indic-parler-tts")
dtok = AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path)

text = "ಶುಭೋದಯ. ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?"
desc = (
    "Suresh's voice is clear, warm, and professional, speaking at a moderate pace. "
    "The recording is of very high quality, with the speaker's voice sounding clear and very close up."
)
di = dtok(desc, return_tensors="pt").to(device)
pi = tok(text, return_tensors="pt").to(device)
print("prompt ids", tuple(pi.input_ids.shape))
with torch.no_grad():
    gen = model.generate(
        input_ids=di.input_ids,
        attention_mask=di.attention_mask,
        prompt_input_ids=pi.input_ids,
        prompt_attention_mask=pi.attention_mask,
        max_new_tokens=1800,
        do_sample=True,
        temperature=0.9,
    )
audio = gen.cpu().numpy().squeeze()
sr = model.config.sampling_rate
print("audio shape", audio.shape, "sr", sr, "secs", float(audio.shape[-1]) / sr)
sf.write("data/tts_output/parler_test2.wav", audio, sr)
print("wrote data/tts_output/parler_test2.wav")
