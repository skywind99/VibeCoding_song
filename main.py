import streamlit as st
import base64
import time
import threading
from datetime import datetime, timedelta

# 페이지 설정
st.set_page_config(
    page_title="🎤 노래 따라부르기",
    page_icon="🎵",
    layout="wide"
)

# CSS 스타일링
st.markdown("""
<style>
    .main-title {
        text-align: center;
        font-size: 3em;
        color: #FF6B6B;
        margin-bottom: 30px;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    
    .lyrics-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 30px;
        border-radius: 20px;
        margin: 20px 0;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    }
    
    .current-line {
        font-size: 2.5em;
        font-weight: bold;
        color: #FFD700;
        text-align: center;
        margin: 20px 0;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
        animation: glow 2s ease-in-out infinite alternate;
    }
    
    .next-line {
        font-size: 1.8em;
        color: #E8E8E8;
        text-align: center;
        margin: 15px 0;
        opacity: 0.8;
    }
    
    .prev-line {
        font-size: 1.5em;
        color: #B8B8B8;
        text-align: center;
        margin: 10px 0;
        opacity: 0.6;
    }
    
    @keyframes glow {
        from { text-shadow: 2px 2px 4px rgba(0,0,0,0.5), 0 0 10px #FFD700; }
        to { text-shadow: 2px 2px 4px rgba(0,0,0,0.5), 0 0 20px #FFD700, 0 0 30px #FFD700; }
    }
    
    .controls {
        text-align: center;
        margin: 30px 0;
    }
    
    .time-display {
        font-size: 1.2em;
        color: #4ECDC4;
        text-align: center;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# 메인 타이틀
st.markdown('<h1 class="main-title">🎤 노래 따라부르기 🎵</h1>', unsafe_allow_html=True)

# 세션 상태 초기화
if 'lyrics' not in st.session_state:
    st.session_state.lyrics = []
if 'current_line_index' not in st.session_state:
    st.session_state.current_line_index = 0
if 'is_playing' not in st.session_state:
    st.session_state.is_playing = False
if 'start_time' not in st.session_state:
    st.session_state.start_time = None

# 사이드바 - 컨트롤 패널
with st.sidebar:
    st.header("🎛️ 컨트롤 패널")
    
    # 오디오 파일 업로드
    uploaded_audio = st.file_uploader(
        "🎵 음악 파일 업로드", 
        type=['mp3', 'wav', 'ogg', 'm4a'],
        help="MP3, WAV, OGG, M4A 파일을 지원합니다"
    )
    
    # 가사 입력
    st.subheader("📝 가사 입력")
    lyrics_input = st.text_area(
        "가사를 한 줄씩 입력하세요:",
        height=200,
        placeholder="첫 번째 줄\n두 번째 줄\n세 번째 줄\n...",
        help="각 줄을 엔터로 구분해서 입력하세요"
    )
    
    # 가사 로드 버튼
    if st.button("📋 가사 로드"):
        if lyrics_input.strip():
            st.session_state.lyrics = [line.strip() for line in lyrics_input.split('\n') if line.strip()]
            st.session_state.current_line_index = 0
            st.success(f"✅ {len(st.session_state.lyrics)}줄의 가사가 로드되었습니다!")
        else:
            st.warning("⚠️ 가사를 입력해주세요!")
    
    # 줄 간격 설정
    line_duration = st.slider(
        "⏱️ 줄 당 시간 (초)",
        min_value=2.0,
        max_value=10.0,
        value=4.0,
        step=0.5,
        help="각 가사 줄이 표시되는 시간을 조절합니다"
    )
    
    # 폰트 크기 설정
    font_scale = st.slider(
        "🔤 폰트 크기",
        min_value=0.5,
        max_value=2.0,
        value=1.0,
        step=0.1,
        help="가사 폰트 크기를 조절합니다"
    )

# 메인 컨텐츠 영역
col1, col2 = st.columns([3, 1])

with col1:
    # 오디오 플레이어
    if uploaded_audio:
        st.audio(uploaded_audio, format='audio/mp3')
        
        # 재생 컨트롤
        control_col1, control_col2, control_col3, control_col4 = st.columns(4)
        
        with control_col1:
            if st.button("▶️ 시작"):
                st.session_state.is_playing = True
                st.session_state.start_time = time.time()
                st.session_state.current_line_index = 0
        
        with control_col2:
            if st.button("⏸️ 일시정지"):
                st.session_state.is_playing = False
        
        with control_col3:
            if st.button("⏹️ 정지"):
                st.session_state.is_playing = False
                st.session_state.current_line_index = 0
                st.session_state.start_time = None
        
        with control_col4:
            if st.button("🔄 리셋"):
                st.session_state.current_line_index = 0
                st.session_state.start_time = time.time() if st.session_state.is_playing else None

with col2:
    # 진행 상황 표시
    if st.session_state.lyrics:
        progress = st.session_state.current_line_index / len(st.session_state.lyrics)
        st.progress(progress)
        st.write(f"📊 진행률: {st.session_state.current_line_index + 1}/{len(st.session_state.lyrics)} 줄")

# 가사 표시 영역
if st.session_state.lyrics:
    # 자동 진행 로직
    if st.session_state.is_playing and st.session_state.start_time:
        elapsed_time = time.time() - st.session_state.start_time
        target_line = int(elapsed_time / line_duration)
        
        if target_line < len(st.session_state.lyrics):
            st.session_state.current_line_index = target_line
        else:
            st.session_state.is_playing = False
    
    # 현재 시간 표시
    if st.session_state.start_time:
        elapsed = time.time() - st.session_state.start_time
        elapsed_formatted = str(timedelta(seconds=int(elapsed)))
        total_time = len(st.session_state.lyrics) * line_duration
        total_formatted = str(timedelta(seconds=int(total_time)))
        st.markdown(f'<div class="time-display">⏰ {elapsed_formatted} / {total_formatted}</div>', unsafe_allow_html=True)
    
    # 가사 표시 컨테이너
    lyrics_container = st.container()
    
    with lyrics_container:
        st.markdown('<div class="lyrics-container">', unsafe_allow_html=True)
        
        current_idx = st.session_state.current_line_index
        
        # 이전 줄 (흐리게)
        if current_idx > 0:
            prev_line = st.session_state.lyrics[current_idx - 1]
            st.markdown(f'<div class="prev-line" style="font-size: {1.5 * font_scale}em;">{prev_line}</div>', unsafe_allow_html=True)
        
        # 현재 줄 (강조)
        if current_idx < len(st.session_state.lyrics):
            current_line = st.session_state.lyrics[current_idx]
            st.markdown(f'<div class="current-line" style="font-size: {2.5 * font_scale}em;">{current_line}</div>', unsafe_allow_html=True)
        
        # 다음 줄 (미리보기)
        if current_idx + 1 < len(st.session_state.lyrics):
            next_line = st.session_state.lyrics[current_idx + 1]
            st.markdown(f'<div class="next-line" style="font-size: {1.8 * font_scale}em;">{next_line}</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # 수동 네비게이션
    nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
    
    with nav_col1:
        if st.button("⬅️ 이전 줄") and st.session_state.current_line_index > 0:
            st.session_state.current_line_index -= 1
    
    with nav_col2:
        # 특정 줄로 이동
        selected_line = st.selectbox(
            "특정 줄로 이동:",
            range(len(st.session_state.lyrics)),
            index=st.session_state.current_line_index,
            format_func=lambda x: f"{x+1}. {st.session_state.lyrics[x][:30]}..."
        )
        if selected_line != st.session_state.current_line_index:
            st.session_state.current_line_index = selected_line
    
    with nav_col3:
        if st.button("➡️ 다음 줄") and st.session_state.current_line_index < len(st.session_state.lyrics) - 1:
            st.session_state.current_line_index += 1

else:
    # 가사가 없을 때 안내 메시지
    st.markdown("""
    <div style="text-align: center; padding: 50px; color: #888;">
        <h3>🎵 시작하기</h3>
        <p>1. 왼쪽 사이드바에서 음악 파일을 업로드하세요</p>
        <p>2. 가사를 입력하고 '가사 로드' 버튼을 클릭하세요</p>
        <p>3. 음악을 재생하고 '시작' 버튼을 눌러 가사를 따라가세요!</p>
    </div>
    """, unsafe_allow_html=True)

# 자동 새로고침 (재생 중일 때만)
if st.session_state.is_playing:
    time.sleep(0.5)
    st.rerun()

# 사용법 안내
with st.expander("📖 사용법 안내"):
    st.markdown("""
    ### 🚗 차량용 노래방 사용법
    
    **1. 준비하기**
    - 사이드바에서 MP3, WAV 등의 음악 파일을 업로드
    - 가사를 한 줄씩 입력 (엔터로 구분)
    - '가사 로드' 버튼 클릭
    
    **2. 설정하기**
    - 줄 당 시간: 각 가사 줄이 표시되는 시간 조절
    - 폰트 크기: 차량에서 보기 편한 크기로 조절
    
    **3. 재생하기**
    - 음악 재생 후 '시작' 버튼 클릭
    - 가사가 자동으로 진행됩니다
    - 수동으로 이전/다음 줄로 이동 가능
    
    **4. 안전 운전**
    - 운전 중에는 조수석 승객이 조작하세요
    - 안전한 곳에 정차 후 설정을 변경하세요
    
    **💡 팁**
    - 태블릿이나 큰 화면에서 사용하면 더 편해요
    - 가사 타이밍이 안 맞으면 '줄 당 시간'을 조절해보세요
    """)
