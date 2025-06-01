import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase, ClientSettings
import av # PyAV: 오디오/비디오 처리를 위한 라이브러리
import numpy as np
from acrcloud.recognizer import ACRCloudRecognizer
import lyricsgenius
import json
import io
import time

# --- 초기 설정 및 세션 상태 ---
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
    st.session_state.audio_buffer = []
if 'is_recording' not in st.session_state:
    st.session_state.is_recording = False
if 'last_recognition_time' not in st.session_state:
    st.session_state.last_recognition_time = 0

# --- API 설정 ---
st.sidebar.header("API 설정 🔑")
st.sidebar.markdown("""
ACRCloud와 Genius API 키가 필요합니다. 각 서비스에 가입하고 키를 발급받으세요.
- [ACRCloud](https://www.acrcloud.com/)
- [Genius API Clients](https://genius.com/api-clients)
""")

# ACRCloud 설정
acr_host = st.sidebar.text_input("ACRCloud Host", value=st.session_state.get("acr_host", ""), type="password")
acr_key = st.sidebar.text_input("ACRCloud Access Key", value=st.session_state.get("acr_key", ""), type="password")
acr_secret = st.sidebar.text_input("ACRCloud Access Secret", value=st.session_state.get("acr_secret", ""), type="password")

# LyricsGenius 설정
genius_token = st.sidebar.text_input("LyricsGenius Client Access Token", value=st.session_state.get("genius_token", ""), type="password")

if acr_host and acr_key and acr_secret:
    st.session_state.acr_config = {
        'host': acr_host,
        'access_key': acr_key,
        'access_secret': acr_secret,
        'recognize_type': ACRCloudRecognizer.ACR_OPT_REC_AUDIO,
        'debug': False,
        'timeout': 10 # seconds
    }
    st.session_state.acr_config_set = True
    st.session_state.acr_host = acr_host # 세션에 저장하여 다음 실행 시 유지
    st.session_state.acr_key = acr_key
    st.session_state.acr_secret = acr_secret
else:
    st.sidebar.warning("ACRCloud 설정을 입력해주세요.")
    st.session_state.acr_config_set = False

if genius_token:
    st.session_state.genius_token_set = True
    st.session_state.genius_token = genius_token # 세션에 저장
else:
    st.sidebar.warning("LyricsGenius 토큰을 입력해주세요.")
    st.session_state.genius_token_set = False

# --- 오디오 처리 클래스 ---
class AudioRecorder(AudioProcessorBase):
    def __init__(self):
        self.audio_buffer = io.BytesIO() # BytesIO 객체로 오디오 데이터 축적
        self.frame_count = 0
        self.sample_rate = 16000 # ACRCloud 권장 샘플링 레이트 중 하나 (16000Hz)
        self.channels = 1 # 모노
        self.bytes_per_sample = 2 # 16-bit 오디오

    def recv(self, frame: av.AudioFrame) -> av.AudioFrame:
        if st.session_state.is_recording:
            # resample 및 mono 변환
            resampled_frame = frame.reformat(format="s16", layout="mono", rate=self.sample_rate)
            chunk = resampled_frame.to_ndarray() # numpy array로 변환 (bytes 대신)
            
            if chunk is not None:
                # numpy array를 bytes로 변환하여 버퍼에 추가
                self.audio_buffer.write(chunk.tobytes())
                self.frame_count += 1
        return frame # 원본 프레임 반환 (streamlit-webrtc에 필요)

    def get_buffer_and_reset(self) -> bytes:
        buffer_value = self.audio_buffer.getvalue()
        self.audio_buffer.seek(0)
        self.audio_buffer.truncate(0)
        self.frame_count = 0
        return buffer_value

# --- 메인 앱 UI ---
st.title("🎶 노래 따라부르기 도우미")
st.markdown("주변에서 재생되는 노래를 인식하고 가사를 찾아줍니다.")

if not st.session_state.acr_config_set or not st.session_state.genius_token_set:
    st.error("먼저 사이드바에서 모든 API 설정을 완료해주세요.")
else:
    # ACRCloud 및 LyricsGenius Recognizer 초기화
    try:
        acr_recognizer = ACRCloudRecognizer(st.session_state.acr_config)
        genius = lyricsgenius.Genius(st.session_state.genius_token, timeout=15, retries=3)
        genius.verbose = False # 너무 많은 로그 출력 방지
        genius.remove_section_headers = True # "[Verse 1]", "[Chorus]" 등 제거 옵션
        genius.skip_non_songs = True
        genius.excluded_terms = ["(Remix)", "(Live)"]

    except Exception as e:
        st.error(f"API 클라이언트 초기화 중 오류 발생: {e}")
        st.stop()

    # WebRTC 스트리머 설정
    ctx = webrtc_streamer(
        key="audio-recorder",
        mode=WebRtcMode.SENDONLY, # 오디오만 보냄
        audio_processor_factory=AudioRecorder,
        client_settings=ClientSettings(
            rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
            media_stream_constraints={"audio": True, "video": False},
        ),
        sendback_audio=False, # 오디오를 다시 클라이언트로 보낼 필요 없음
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎤 녹음 시작", disabled=st.session_state.is_recording):
            st.session_state.is_recording = True
            st.session_state.audio_buffer = [] # 이전 버퍼 초기화
            st.info("녹음 중... (약 10초간 노래를 들려주세요)")

    with col2:
        if st.button("🛑 녹음 중지 및 노래 찾기", disabled=not st.session_state.is_recording):
            st.session_state.is_recording = False
            st.info("녹음 중지. 노래를 분석합니다...")

            current_time = time.time()
            if current_time - st.session_state.last_recognition_time < 15: # API 호출 제한 (15초)
                st.warning(f"API 호출 빈도가 너무 잦습니다. {15 - int(current_time - st.session_state.last_recognition_time)}초 후에 다시 시도해주세요.")
            elif ctx.audio_processor:
                audio_data = ctx.audio_processor.get_buffer_and_reset()
                
                if not audio_data or len(audio_data) < 16000 * 2 * 3: # 최소 3초 분량의 데이터 (16kHz, 16bit, mono)
                    st.warning("녹음된 오디오가 너무 짧습니다. 다시 시도해주세요.")
                else:
                    st.session_state.last_recognition_time = current_time
                    with st.spinner("노래 인식 중... 🤔"):
                        try:
                            # ACRCloud는 파일 경로 또는 파일 버퍼를 받을 수 있음.
                            # 여기서는 바이트 스트림을 인식 함수에 직접 전달
                            # recognize_by_filebuffer(file_buffer, start_seconds, rec_length (0 for full))
                            result_json_str = acr_recognizer.recognize_by_filebuffer(audio_data, 0, 10) # 처음 10초
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
