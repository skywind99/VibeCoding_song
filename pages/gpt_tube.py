import streamlit as st
from youtubesearchpython import VideosSearch
import lyricsgenius

# Genius API 설정
GENIUS_API_TOKEN = "여기에_당신의_토큰"
genius = lyricsgenius.Genius(GENIUS_API_TOKEN)

st.title("🎶 노래 검색해서 따라불러요")

query = st.text_input("노래 제목이나 가사 일부를 입력하세요", "")

if query:
    videosSearch = VideosSearch(query, limit=5)
    results = videosSearch.result()['result']
    
    options = [f"{v['title']} - {v['channel']['name']}" for v in results]
    selected = st.selectbox("노래를 선택하세요", options)

    if selected:
        idx = options.index(selected)
        video_id = results[idx]['id']
        video_title = results[idx]['title']
        
        # 유튜브 재생
        st.markdown(f"## ▶️ {video_title}")
        st.video(f"https://www.youtube.com/watch?v={video_id}")
        
        # 가사 검색
        try:
            song = genius.search_song(video_title)
            if song:
                st.subheader("📄 가사")
                st.text(song.lyrics)
            else:
                st.warning("가사를 찾을 수 없습니다.")
        except:
            st.error("가사 검색 중 오류 발생.")
