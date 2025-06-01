import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase # ClientSettings 임포트 제거
import av
import numpy as np
from acrcloud.recognizer import ACRCloudRecognizer
import lyricsgenius
import json
import io
import time
from acrcloud.recognizer import ACRCloudRecognizer, ACR_OPT_REC_AUDIO
# --- 초기 설정 및 세션 상태 ---
# (이전 코드와 동일하게 유지)
if 'song_title' not in st.session_state:
    st.session_state.song_title = None
if 'artist_name' not in st.session_state:
    st.session_state.artist_name = None
if 'lyrics' not in st.session_state:
    st.session_state.lyrics = None
if 'acr_config_set' not in st.session_state:
    st.session_state.acr_config_set = False
if 'genius_token_set' not in st.session_state:
    st.session_state.genius_token_set = False
if 'audio_buffer' not in st.session_state:
    st.session_state.audio_buffer = [] # BytesIO 대신 리스트로 시작했다가 필요시 변환 고려
if 'is_recording' not in st.session_state:
    st.session_state.is_recording = False
if 'last_recognition_time' not in st.session_state:
    st.session_state.last_recognition_time = 0

# --- API 설정 ---
# (이전 코드와 동일하게 유지)
st.sidebar.header("API 설정 🔑")
st.sidebar.markdown("""
ACRCloud와 Genius API 키가 필요합니다. 각 서비스에 가입하고 키를 발급받으세요.
- [ACRCloud](https://www.acrcloud.com/)
- [Genius API Clients](https://genius.com/api-clients)
""")

acr_host = st.sidebar.text_input("ACRCloud Host", value=st.session_state.get("acr_host", ""), type="password")
acr_key = st.sidebar.text_input("ACRCloud Access Key", value=st.session_state.get("acr_key", ""), type="password")
acr_secret = st.sidebar.text_input("ACRCloud Access Secret", value=st.session_state.get("acr_secret", ""), type="password")
genius_token = st.sidebar.text_input("LyricsGenius Client Access Token", value=st.session_state.get("genius_token", ""), type="password")

if acr_host and acr_key and acr_secret:
    st.session_state.acr_config = {
        'host': acr_host,
        'access_key': acr_key,
        'access_secret': acr_secret,
        'recognize_type': ACRCloudRecognizer.ACR_OPT_REC_AUDIO,
        'debug': False,
        'timeout': 10 
    }
    st.session_state.acr_config_set = True
    st.session_state.acr_host = acr_host 
    st.session_state.acr_key = acr_key
    st.session_state.acr_secret = acr_secret
else:
    st.sidebar.warning("ACRCloud 설정을 입력해주세요.")
    st.session_state.acr_config_set = False

if genius_token:
    st.session_state.genius_token_set = True
    st.session_state.genius_token = genius_token 
else:
    st.sidebar.warning("LyricsGenius 토큰을 입력해주세요.")
    st.session_state.genius_token_set = False

# --- 오디오 처리 클래스 ---
class AudioRecorder(AudioProcessorBase):
    def __init__(self):
        self.audio_buffer_list = [] # 프레임 데이터를 모으기 위한 리스트
        self.sample_rate = 16000 
        self.channels = 1 
        self.bytes_per_sample = 2 

    def recv(self, frame: av.AudioFrame) -> av.AudioFrame:
        if st.session_state.is_recording:
            resampled_frame = frame.reformat(format="s16", layout="mono", rate=self.sample_rate)
            chunk_bytes = resampled_frame.to_ndarray().tobytes() # 바이트로 변환
            self.audio_buffer_list.append(chunk_bytes)
        return frame 

    def get_buffer_and_reset(self) -> bytes:
        # 리스트에 있는 모든 바이트 청크를 하나로 합침
        buffer_value = b"".join(self.audio_buffer_list)
        self.audio_buffer_list = [] # 버퍼 리셋
        return buffer_value

# --- 메인 앱 UI ---
st.title("🎶 노래 따라부르기 도우미")
st.markdown("주변에서 재생되는 노래를 인식하고 가사를 찾아줍니다.")

if not st.session_state.acr_config_set or not st.session_state.genius_token_set:
    st.error("먼저 사이드바에서 모든 API 설정을 완료해주세요.")
else:
    try:
        acr_recognizer = ACRCloudRecognizer(st.session_state.acr_config)
        genius = lyricsgenius.Genius(st.session_state.genius_token, timeout=15, retries=3)
        genius.verbose = False 
        genius.remove_section_headers = True 
        genius.skip_non_songs = True
        genius.excluded_terms = ["(Remix)", "(Live)"]
    except Exception as e:
        st.error(f"API 클라이언트 초기화 중 오류 발생: {e}")
        st.stop()

    # WebRTC 스트리머 설정 수정
    # ClientSettings를 제거하고, rtc_configuration과 media_stream_constraints를 직접 인자로 전달
    ctx = webrtc_streamer(
        key="audio-recorder",
        mode=WebRtcMode.SENDONLY, 
        audio_processor_factory=AudioRecorder,
        rtc_configuration={ # 직접 전달
            "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
        },
        media_stream_constraints={ # 직접 전달
            "audio": True,
            "video": False
        },
        sendback_audio=False,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎤 녹음 시작", disabled=st.session_state.is_recording):
            st.session_state.is_recording = True
            if ctx.audio_processor: # audio_processor가 준비되었는지 확인
                 ctx.audio_processor.audio_buffer_list = [] # 버퍼 초기화
            st.info("녹음 중... (약 10초간 노래를 들려주세요)")

    with col2:
        if st.button("🛑 녹음 중지 및 노래 찾기", disabled=not st.session_state.is_recording):
            st.session_state.is_recording = False
            st.info("녹음 중지. 노래를 분석합니다...")

            current_time = time.time()
            if current_time - st.session_state.last_recognition_time < 15: 
                st.warning(f"API 호출 빈도가 너무 잦습니다. {15 - int(current_time - st.session_state.last_recognition_time)}초 후에 다시 시도해주세요.")
            elif ctx.audio_processor:
                audio_data = ctx.audio_processor.get_buffer_and_reset()
                
                if not audio_data or len(audio_data) < self.sample_rate * self.bytes_per_sample * 3: # audio_processor의 샘플링 정보 사용
                    st.warning("녹음된 오디오가 너무 짧습니다. 다시 시도해주세요.")
                else:
                    st.session_state.last_recognition_time = current_time
                    with st.spinner("노래 인식 중... 🤔"):
                        try:
                            result_json_str = acr_recognizer.recognize_by_filebuffer(audio_data, 0, 10) 
                            result = json.loads(result_json_str)
                        except Exception as e:
                            st.error(f"ACRCloud API 호출 중 오류 발생: {e}")
                            result = None
                            
                    if result and result.get('status', {}).get('code') == 0 and 'metadata' in result:
                        music_info = result['metadata']['music'][0]
                        title = music_info['title']
                        artists_list = [artist['name'] for artist in music_info.get('artists', [])]
                        artist_str = ", ".join(artists_list)
                        
                        st.session_state.song_title = title
                        st.session_state.artist_name = artist_str
                        st.success(f"🎵 노래 찾음: **{title}** - {artist_str}")

                        with st.spinner("가사 검색 중... 📜"):
                            try:
                                song = genius.search_song(title, artist_str)
                                if song:
                                    st.session_state.lyrics = song.lyrics
                                else:
                                    st.session_state.lyrics = "😭 해당 곡의 가사를 찾을 수 없습니다."
                            except Exception as e:
                                st.error(f"LyricsGenius API 호출 중 오류 발생: {e}")
                                st.session_state.lyrics = "⚠️ 가사 검색 중 오류가 발생했습니다."
                    elif result:
                        st.warning(f"노래를 인식하지 못했습니다. (ACRCloud 응답 코드: {result.get('status', {}).get('msg')})")
                        st.session_state.song_title = None
                        st.session_state.artist_name = None
                        st.session_state.lyrics = None
                    else:
                        st.error("노래 인식에 실패했습니다. ACRCloud에서 응답이 없습니다.")
                        st.session_state.song_title = None
                        st.session_state.artist_name = None
                        st.session_state.lyrics = None
            else:
                st.warning("오디오 프로세서가 아직 준비되지 않았습니다.")


    # --- 결과 표시 ---
    if st.session_state.song_title:
        st.subheader(f"🎶 {st.session_state.song_title} - {st.session_state.artist_name}")
        if st.session_state.lyrics:
            st.text_area("가사", st.session_state.lyrics, height=400)
        else:
            st.info("가사를 기다리는 중이거나 찾을 수 없습니다.")

st.sidebar.markdown("---")
st.sidebar.info("Made by Gemini for a car sing-along experience.")
