"""复现 NO BATIDÃO 歌词不匹配问题"""
import sys
sys.path.insert(0, '/workspace')
from mp import OnlineLyricsFetcher, LyricsDisplay
from pathlib import Path

fetcher = OnlineLyricsFetcher()
keyword = "NO BATIDÃO"

# 收集候选
candidates = fetcher._collect_candidates(keyword)
print(f"候选数: {len(candidates)}")
for i, c in enumerate(candidates):
    s = fetcher._score_candidate(keyword, c)
    print(f"  {i+1}. score={s:4d}  {c[1]} - {c[0]} ({c[2]})")

# 评分排序
scored = [(c, fetcher._score_candidate(keyword, c)) for c in candidates]
positive = [c for c, s in scored if s >= 0]
ordered = positive if positive else [c for c, _ in scored]
ordered.sort(key=lambda c: fetcher._score_candidate(keyword, c), reverse=True)

print("\n=== 排序后 ===")
for i, c in enumerate(ordered):
    s = fetcher._score_candidate(keyword, c)
    print(f"  {i+1}. score={s:4d}  {c[1]} - {c[0]} ({c[2]})")

# 逐个尝试，看实际获取的歌词
print("\n=== 逐个尝试获取歌词 ===")
for i, cand in enumerate(ordered[:5]):
    lrc = fetcher._fetch_lyric_by_candidate(cand)
    has_timeline = fetcher._has_timeline(lrc)
    ld = LyricsDisplay(Path('/tmp/test.mp3'))
    ld._parse_lrc(lrc)
    print(f"\n  {i+1}. {cand[2]}: {cand[1]} - {cand[0]}")
    print(f"     有效={has_timeline}, 行数={len(ld.lyrics)}")
    if ld.lyrics:
        print(f"     首行: {ld.lyrics[0][1][:60]}")
        print(f"     前3行歌词:")
        for ts, text in ld.lyrics[:3]:
            print(f"       [{ts:.2f}] {text[:60]}")

# 实际选中的
status, lrc, source = fetcher.search_first(keyword)
print(f"\n=== 最终选中 ===")
print(f"状态: {status}, 来源: {source}")
if lrc:
    ld = LyricsDisplay(Path('/tmp/test.mp3'))
    ld._parse_lrc(lrc)
    print(f"行数: {len(ld.lyrics)}")
    print("前5行:")
    for ts, text in ld.lyrics[:5]:
        print(f"  [{ts:.2f}] {text[:60]}")
