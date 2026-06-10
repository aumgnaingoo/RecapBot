import os
import re
import tempfile
import asyncio
import urllib.request
import streamlit as st
from google import genai

# ==========================================
# C O N F I G U R A T I O N & SERVERS
# ==========================================
GEMINI_SERVERS = {
    "Server 1": "Ab8RN6JWlQI2BLk0ec7iQAlj1EykGJTsRksNpfQuOC-Ir3czLA",
    "Server 2": "AQ.Ab8RN6L3lkQVRqM8Z-9eISP0ZFlk_4U5aY1dVw9b3sVHCIf3Cg",
    "Server 3": "AQ.Ab8RN6LmFuJbV2MeO3TDHhzZz6ffMjTPUunToMOmGfZ8AWkwng.",
    "Server 4": "AQ.Ab8RN6Lo3Qo4VWmG6ly-SvTtj0ELvTvb_5rzrEuLTzSO4-I4lAlA",
    "Server 5": "AQ.Ab8RN6LxtWk7KR-mswJ0YqY2DiKBOtFpmQ46CXGN-Hl7LAxLgg",
    "Server 6": "AIzaSyCUZiUuvDPSeNrC4UN_TIKaXtk2HCovXW0",
    "Server 7": "AIzaSyDHjV3ANcYHmMXI7HLAr6hlBkdCu-tSdkc",
    "Server 8 (Default)": "AIzaSyC2HBCyX0mPCg--tKIqkYqp36G-PntfdEg"
}

VOICE_TYPE = "my-MM-NilarNeural" 
ORIGINAL_AUDIO = "keep"          

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def ms_to_time(ms: int) -> str:
    s = ms // 1000
    m = s // 60
    h = m // 60
    return f"{h:02d}:{(m%60):02d}:{(s%60):02d},{ms%1000:03d}"

def time_to_ms(time_str: str) -> int:
    time_str = time_str.replace(',', '.')
    parts = time_str.split(':')
    h = int(parts[0])
    m = int(parts[1])
    s_parts = parts[2].split('.')
    s = int(s_parts[0])
    ms = int(s_parts[1][:3].ljust(3, '0')) if len(s_parts) > 1 else 0
    return h * 3600000 + m * 60000 + s * 1000 + ms

async def get_media_duration(filepath: str) -> float:
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', filepath]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, _ = await proc.communicate()
    try: return float(stdout.decode().strip())
    except: return 0.0

async def has_audio_stream(filepath: str) -> bool:
    cmd = ['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=codec_type', '-of', 'default=noprint_wrappers=1:nokey=1', filepath]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, _ = await proc.communicate()
    return len(stdout.decode().strip()) > 0

# ==========================================
# STREAMLIT UI & CORE LOGIC
# ==========================================
st.set_page_config(page_title="AI Myanmar Video Translator", page_icon="🎬", layout="centered")

st.title("🎬 AI Myanmar Video Translator & Recapper")
st.write("ဗီဒီယိုများကို မြန်မာဘာသာပြန်ဆိုပြီး AI မြန်မာအသံထွက်နှင့် စာတန်းထိုး ထည့်သွင်းပေးသည့် ဝက်ဘ်ဆိုက်")

# Sidebar သို့မဟုတ် Main Page တွင် Server ရွေးခိုင်းခြင်း
selected_server_name = st.selectbox("🖥 အသုံးပြုမည့် Gemini API Server ကိုရွေးချယ်ပါ", list(GEMINI_SERVERS.keys()), index=7)
current_api_key = GEMINI_SERVERS[selected_server_name]

# File Uploader
uploaded_file = st.file_uploader("📥 ဘာသာပြန်မည့် ဗီဒီယိုဖိုင်ကို ရွေးချယ်တင်ပြပါ (Max: 20MB)", type=["mp4", "mkv", "avi", "mov"])

if uploaded_file is not None:
    st.video(uploaded_file) # မူရင်းဗီဒီယိုအား အစမ်းပြသခြင်း
    
    if st.button("🚀 ဗီဒီယိုအား မြန်မာမှုပြုလုပ်မည်", type="primary"):
        status_box = st.empty()
        progress_bar = st.progress(0)
        
        try:
            client = genai.Client(api_key=current_api_key)
            
            # ယာယီအလုပ်လုပ်မည့် ပတ်ဝန်းကျင်ဆောက်ခြင်း
            with tempfile.TemporaryDirectory() as work_dir:
                video_path = os.path.join(work_dir, "input.mp4")
                
                with open(video_path, "wb") as f:
                    f.write(uploaded_file.read())
                
                # --- 1. Audio Extraction ---
                status_box.info("🎵 အဆင့် ၁ - ဗီဒီယိုမှ အသံကို ခွဲထုတ်နေပါသည်...")
                progress_bar.progress(15)
                audio_prefix = os.path.join(work_dir, "audio_%03d.mp3")
                
                extract_cmd = ['ffmpeg', '-i', video_path, '-q:a', '0', '-map', 'a', '-f', 'segment', '-segment_time', '45', audio_prefix, '-y']
                proc = await asyncio.create_subprocess_exec(*extract_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                await proc.communicate()
                
                chunk_files = sorted([f for f in os.listdir(work_dir) if f.startswith('audio_') and f.endswith('.mp3')])
                if not chunk_files:
                    st.error("❌ ဗီဒီယိုထဲတွင် အသံဖိုင် (Audio Stream) မပါဝင်ပါ။")
                    st.stop()

                all_subs = []
                
                # --- 2. AI Translation ---
                status_box.info(f"🤖 အဆင့် ၂ - Gemini AI ဖြင့် မြန်မာလို ဘာသာပြန်ဆိုနေပါသည်...")
                progress_bar.progress(35)
                
                for c_idx, c_file in enumerate(chunk_files):
                    c_path = os.path.join(work_dir, c_file)
                    offset_secs = c_idx * 45
                    
                    uploaded_audio = client.files.upload(file=c_path, config={'mime_type': 'audio/mp3'})
                    
                    prompt = (
                        "Listen to this audio segment and translate the spoken content directly into Burmese (Myanmar). "
                        "YOU MUST OUTPUT THE TRANSLATION STRICTLY AND ONLY IN VALID SRT (SubRip) FORMAT. "
                        "Output the translated text in the Burmese alphabet (မြန်မာစာ) only. Include accurate timestamps. "
                        "Limit subtitle line lengths to max 40 characters."
                    )
                    
                    res = client.models.generate_content(model='gemini-2.5-flash', contents=[uploaded_audio, prompt])
                    srt_text = res.text
                    client.files.delete(name=uploaded_audio.name)
                    
                    # SRT Parsing Logic
                    lines = srt_text.split('\n')
                    time_indices = [i for i, line in enumerate(lines) if '-->' in line]
                    for i, time_idx in enumerate(time_indices):
                        time_line = lines[time_idx]
                        match = re.search(r'(\d{1,2}:\d{2}:\d{2}(?:[.,]\d{1,3})?)\s*-->\s*(\d{1,2}:\d{2}:\d{2}(?:[.,]\d{1,3})?)', time_line)
                        if not match: continue
                        
                        start_ms = time_to_ms(match.group(1)) + (offset_secs * 1000)
                        end_ms = time_to_ms(match.group(2)) + (offset_secs * 1000)
                        
                        text_end_idx = time_indices[i+1] if i < len(time_indices) - 1 else len(lines)
                        text_lines = lines[time_idx+1:text_end_idx]
                        clean_text = " ".join([l.strip() for l in text_lines if not re.match(r'^\d+$', l.strip())]).strip()
                        
                        if clean_text:
                            all_subs.append({'start_ms': start_ms, 'end_ms': end_ms, 'text': clean_text})
                    
                    if c_idx < len(chunk_files) - 1: await asyncio.sleep(5)

                if not all_subs:
                    st.error("❌ ဘာသာပြန်ဆိုရန် အသံစာသား ရှာမတွေ့ပါ။ API Key သေဆုံးနေခြင်းလည်း ဖြစ်နိုင်ပါသည်။")
                    st.stop()

                # --- 3. Clean SRT & Save ---
                all_subs.sort(key=lambda x: x['start_ms'])
                clean_srt = ""
                for idx, sub in enumerate(all_subs):
                    clean_srt += f"{idx + 1}\r\n{ms_to_time(sub['start_ms'])} --> {ms_to_time(sub['end_ms'])}\r\n{sub['text']}\r\n\r\n"
                
                srt_path = os.path.join(work_dir, "subs.srt")
                with open(srt_path, "w", encoding="utf-8") as f: f.write(clean_srt)
                    
                # --- 4. TTS Generation ---
                status_box.info("🗣 အဆင့် ၃ - AI မြန်မာအသံထွက်များ ဖန်တီးနေပါသည်...")
                progress_bar.progress(60)
                chunk_paths = []
                for i, sub in enumerate(all_subs):
                    tts_path = os.path.join(work_dir, f"tts_{i}.mp3")
                    cmd = ['edge-tts', '--voice', VOICE_TYPE, '--text', sub['text'], '--write-media', tts_path]
                    p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                    await p.communicate()
                    if os.path.exists(tts_path):
                        chunk_paths.append({'path': tts_path, 'start_ms': sub['start_ms'], 'end_ms': sub['end_ms']})

                # --- 5. Font Download ---
                font_path = os.path.join(work_dir, 'NotoSansMyanmar-Regular.ttf')
                try: urllib.request.urlretrieve('https://github.com/google/fonts/raw/main/ofl/notosansmyanmar/NotoSansMyanmar-Regular.ttf', font_path)
                except: pass
                
                fonts_conf = os.path.join(work_dir, 'fonts.conf')
                with open(fonts_conf, 'w') as f:
                    f.write(f'<?xml version="1.0"?><fontconfig><dir>{work_dir}</dir><cachedir>/tmp/fonts-cache</cachedir></fontconfig>')

                # --- 6. FFmpeg Video Multiplexing ---
                status_box.info("🎬 အဆင့် ၄ - ဗီဒီယိုနှင့် အသံ/စာတန်းထိုးများကို ပေါင်းစပ်နေပါသည်...")
                progress_bar.progress(80)
                out_video = os.path.join(work_dir, "output.mp4")
                
                has_audio = await has_audio_stream(video_path)
                keep_original = ORIGINAL_AUDIO == 'keep' and has_audio
                use_audio_mix = len(chunk_paths) > 0
                video_duration = await get_media_duration(video_path)
                if video_duration <= 0: video_duration = 1.0

                args = ['ffmpeg', '-y', '-i', video_path]
                filter_graph = ""
                
                if use_audio_mix:
                    if keep_original: filter_graph += "[0:a]volume=1.0[orig_a];"
                    elif has_audio: filter_graph += "[0:a]volume=0.0[orig_a];"
                    else: filter_graph += f"anullsrc=channel_layout=stereo:sample_rate=44100:d={video_duration}[orig_a];"

                    tts_amix_str = ""
                    tts_inputs = 0
                    last_end_ms = 0
                    
                    for i, c in enumerate(chunk_paths):
                        args.extend(['-i', c['path']])
                        input_idx = i + 1
                        safe_start_ms = max(c['start_ms'], last_end_ms + 200)
                        in_duration = await get_media_duration(c['path'])
                        if in_duration <= 0: in_duration = 1.0
                        target_duration = max(0.1, (c['end_ms'] - safe_start_ms) / 1000)
                        ratio = max(0.85, min(in_duration / target_duration, 1.6))
                        last_end_ms = safe_start_ms + ((in_duration / ratio) * 1000)

                        atempo_str = f"atempo={ratio}"
                        pad_ms = round(safe_start_ms)
                        filter_graph += f"[{input_idx}:a]{atempo_str},adelay={pad_ms}|{pad_ms}[a{i}];"
                        tts_amix_str += f"[a{i}]"
                        tts_inputs += 1

                    if tts_inputs > 1: filter_graph += f"{tts_amix_str}amix=inputs={tts_inputs}:duration=longest,apad[ttsmix];"
                    elif tts_inputs == 1: filter_graph += f"{tts_amix_str}apad[ttsmix];"

                    if keep_original:
                        filter_graph += f"[ttsmix]asplit=2[tts_sc][tts_out];"
                        filter_graph += f"[orig_a][tts_sc]sidechaincompress=threshold=0.04:ratio=6.0:attack=10:release=400[ducked_orig];"
                        filter_graph += f"[ducked_orig][tts_out]amix=inputs=2:duration=first:dropout_transition=0,volume=2[outa]"
                    else:
                        filter_graph += f"[orig_a][ttsmix]amix=inputs=2:duration=first:dropout_transition=0,volume=2[outa]"

                safe_srt = srt_path.replace('\\', '/').replace(":", "\\\\:")
                safe_dir = work_dir.replace('\\', '/').replace(":", "\\\\:")
                
                if use_audio_mix:
                    filter_graph += f";[0:v]subtitles='{safe_srt}':fontsdir='{safe_dir}':force_style='Fontname=Noto Sans Myanmar,FontSize=24,MarginV=20'[outv]"
                    args.extend(['-filter_complex', filter_graph, '-map', '[outv]', '-map', '[outa]'])
                else:
                    args.extend(['-vf', f"subtitles='{safe_srt}':fontsdir='{safe_dir}':force_style='Fontname=Noto Sans Myanmar,FontSize=24,MarginV=20'", '-map', '0:v'])
                    if has_audio: args.extend(['-map', '0:a'])
                
                args.extend(['-c:v', 'libx264', '-preset', 'fast', '-crf', '28'])
                if use_audio_mix: args.extend(['-c:a', 'aac', '-b:a', '128k'])
                elif has_audio: args.extend(['-c:a', 'copy'])
                args.append(out_video)
                
                env = os.environ.copy()
                env['FONTCONFIG_FILE'] = fonts_conf
                proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env)
                await proc.communicate()

                # --- 7. Final Presentation ---
                if os.path.exists(out_video):
                    status_box.success("🎉 အောင်မြင်စွာ ဘာသာပြန်ဆိုပြီးပါပြီ။")
                    progress_bar.progress(100)
                    
                    with open(out_video, "rb") as file_data:
                        st.video(file_data.read()) # Web ပေါ်တွင် တန်းပြခြင်း
                        
                        # Download Button ချပေးခြင်း
                        file_data.seek(0)
                        st.download_button(
                            label="📥 ဘာသာပြန်ပြီးသား ဗီဒီယိုကိုသိမ်းဆည်းရန် နှိပ်ပါ",
                            data=file_data.read(),
                            file_name="translated_myanmar.mp4",
                            mime="video/mp4"
                        )
                else:
                    st.error("❌ ဗီဒီယို ပေါင်းစပ်မှု မအောင်မြင်ပါ။")

        except Exception as e:
            st.error(f"❌ အမှားအယွင်းဖြစ်ပွားသည် - {str(e)}")

if __name__ == '__main__':
    import asyncio
    try: asyncio.run(main())
    except: pass
