import mcp
from mcp.client.streamable_http import streamablehttp_client
from dateutil.relativedelta import relativedelta
from datetime import datetime
import asyncio
import base64
import json
import re

from dotenv import load_dotenv
import os


# simithery_api_key
load_dotenv('../unified_agent_system/.env') # 디버깅으로 킬 때는 ./unfied
smithery_api_key=os.getenv("SMITHERY_API_KEY")
google_api_key=os.getenv("GOOGLE_API_KEY")

print(f"smithery_api_key : {smithery_api_key}")
# smithery_mcp_url
app_store_url = (
    "https://server.smithery.ai/@JiantaoFu/appinsightmcp/mcp"
    f"?api_key={smithery_api_key}&profile=blank-tahr-7BPYtb"
)
amazon_url = (
    f"https://server.smithery.ai/@SiliconValleyInsight/amazon-product-search/mcp"
    f"?api_key={smithery_api_key}&profile=blank-tahr-7BPYtb"
)

bright_data_url = (
    f"https://server.smithery.ai/@luminati-io/brightdata-mcp/mcp"
    f"?api_key={smithery_api_key}&profile=blank-tahr-7BPYtb"
)

youtube_config = {
    "youtubeTranscriptLang": "ko",
    "youtubeApiKey": os.getenv("YOUTUBE_API_KEY"),
}
youtube_config_b64 = base64.b64encode(json.dumps(youtube_config).encode()).decode()

youtube_url = f"https://server.smithery.ai/@icraft2170/youtube-data-mcp-server/mcp?config={youtube_config_b64}&api_key={smithery_api_key}&profile=blank-tahr-7BPYtb"


##########################################################################

async def get_trending_new_app(url):
    answer = ["[한국 App Store에서 신규 인기 앱] "]
    async with streamablehttp_client(url) as (read_stream, write_stream, _):
        async with mcp.ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            #🇰🇷 앱스토어 신규인기앱
            params = {
                "collection": "newapplications",
                "country": "kr",
                #"num": max_results,
            }
               
         
            result = await session.call_tool("app-store-list", params)
            apps = json.loads(result.content[0].text)
                
            if isinstance(apps, dict):
                apps = apps.get("apps", [])
            for i, app in enumerate(apps, 1):
                answer.append(f"{i}. {app.get('title')} | {app.get('genre')}")
    return "\n".join(answer)      


async def get_trending_amazon_products(url=amazon_url, max_results=20):
    answer = ["[아마존 트렌딩 상품] "]
    async with streamablehttp_client(url) as (read_stream, write_stream, _):
        async with mcp.ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            search_input = {
                "query": f"아마존 top {max_results} 트렌딩 상품이 뭐야?",
                "maxResults": max_results,
            }
            result = await session.call_tool("find_products_to_buy", search_input)
            result_text = result.content[0].text
            
            # 정제
            products = parse_amazon_plain_text_products(result_text, max_results=max_results)
            for idx, item in enumerate(products, 1):
                title = item.get("title", "제목없음")
                price = item.get("price", "(가격정보없음)")
               
                answer.append(
                    f"{idx}. {title} - 가격: {price}\n"
                )
    return "\n".join(answer)

async def get_trending_youtube_videos(
    youtube_url: str,
    region_code: str = "KR",
    max_results: int = 15,
    category_id: int | None = None
) -> str:
  
    async with streamablehttp_client(youtube_url) as (read_stream, write_stream, _):
        async with mcp.ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            trending_input = {
                "regionCode": region_code,
                "maxResults": max_results,
            }
            if category_id is not None:
                trending_input["categoryId"] = str(category_id)

            trending_result = await session.call_tool("getTrendingVideos", trending_input)
            trending_json = trending_result.content[0].text
            trending_videos = json.loads(trending_json)

            video_ids = [item["id"] for item in trending_videos]
            details_result = await session.call_tool("getVideoDetails", {"videoIds": video_ids})
            details_json = details_result.content[0].text
            details_dict = json.loads(details_json)

            output_lines = []
            output_lines.append(f"🔥 유튜브 인기 영상 TOP {max_results} 상세\n")
            for rank, video_id in enumerate(video_ids, 1):
                detail = details_dict.get(video_id)
                if not detail:
                    output_lines.append(f"top{rank}. 정보 없음\n")
                    continue

                snippet    = detail.get("snippet", {})
                statistics = detail.get("statistics", {})
                content_details = detail.get("contentDetails", {})

                tags       = snippet.get("tags", [])
                title      = snippet.get("title")
                channel    = snippet.get("channelTitle")
                duration_iso = content_details.get("duration") or ""
                duration_str = parse_duration(duration_iso)
                description= snippet.get("description", "").strip()
                view       = statistics.get("viewCount")
                like       = statistics.get("likeCount")
                comment    = statistics.get("commentCount")
                published  = snippet.get("publishedAt")

                output_lines.append(
                    f"top{rank}. [{title}]\n"
                    f"채널: {channel}\n"
                    f"영상링크: https://youtube.com/watch?v={video_id}\n"
                    f"영상길이: {duration_str}\n"
                    f"태그: {', '.join(tags) if tags else '(없음)'}\n"
                    f"설명: {description}\n"
                    f"조회수: {view}\n"
                    f"좋아요수: {like}\n"
                    f"댓글수: {comment}\n"
                    f"업로드일: {published}\n"
                )

            return "\n".join(output_lines)


def parse_amazon_plain_text_products(raw_text, max_results=5):
    lines = raw_text.splitlines()
    products = []
    curr = {}
    for line in lines:
        line = line.strip()
        m = re.match(r"^(\d+)\.\s+(.*)", line)
        if m:
            if curr:
                products.append(curr)
                if len(products) >= max_results:
                    break
                curr = {}
            curr['title'] = m.group(2)
        elif line.startswith("Price:"):
            curr['price'] = line.replace("Price:", "").strip()
        elif line.startswith("Image:"):
            curr['image'] = line.replace("Image:", "").strip()
        elif line.startswith("Product Link:"):
            curr['product_url'] = line.replace("Product Link:", "").strip()
        elif line and not line.startswith("Found "):
            if 'short_desc' not in curr:
                curr['short_desc'] = line
    if curr and len(products) < max_results:
        products.append(curr)
    return products[:max_results]

YOUTUBE_CATEGORY_KR_DICT = {
    1:  "영화 및 애니메이션",
    2:  "자동차 및 차량",
    10: "음악",
    15: "반려동물 및 동물",
    17: "스포츠",
    19: "여행 및 이벤트",
    20: "게임",
    22: "인물 & 블로그",
    23: "코미디",
    24: "엔터테인먼트",
    25: "뉴스 및 정치",
    26: "Howto & Style (요리/스타일/먹방 등)",
    27: "교육",
    28: "과학 및 기술",
}

def parse_duration(iso_duration):
    """ISO8601 PT#H#M#S → 'M분 S초' 또는 'H시간 M분 S초' 변환"""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration)
    if not match:
        return "?"
    h = int(match.group(1) or 0)
    m = int(match.group(2) or 0)
    s = int(match.group(3) or 0)
    if h:
        return f"{h}시간 {m}분 {s}초"
    return f"{m}분 {s}초" if m or s else "0초"


today=datetime.now()
min_date = today - relativedelta(years=1,months=6)

async def get_common(url,query, max_results=2):
    print("[DEBUG] get_common 진입")
    try:
        answer = []
        async with streamablehttp_client(url) as (read_stream, write_stream, _):
            async with mcp.ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                
                params = {"query": query, "engine": "google", "min_date": min_date}
                search_result = await session.call_tool("search_engine", params)
                # try:
                #     text = search_result.content[0].text
                # except Exception as e:
                #     print(f"[ERROR] search_engine 결과 접근 실패: {e}")
                #     return "검색 실패"
                if not hasattr(search_result, "content") or not search_result.content:
                    print("[ERROR] search_engine 응답이 비정상")
                    return "검색 실패"
                text = getattr(search_result.content[0], "text", "")
                
                url_pattern = re.compile(r"\(http[^)]+\)")
                url_candidates = url_pattern.findall(text)
                links = [s[1:-1] for s in url_candidates]

                try:
                    links = links[6:] # 구글 부가링크 제외
                    print(links)
                    if len(links) < 1:
                        raise ValueError
                except Exception:
                    return "\n[!] URL 추출을 위한 검색 결과가 너무 적습니다.\n검색어를 더 구체적으로 바꾸거나, 다른 키워드로 재시도해 주세요."

                # 2. 본문 수집 (에러 없는 2개까지)
                collected_texts = []
                count = 0
                for url_ in links:
                    if count >= max_results:
                        break
                    try:
                        scrape_result = await session.call_tool("scrape_as_markdown", {"url": url_})
                        if not getattr(scrape_result, "isError", False):
                            content = (scrape_result.content[0].text or '').strip()
                            if len(content)<=100:
                                continue
                            collected_texts.append(content)
                            count += 1
                    except Exception as e:
                        continue

                if not collected_texts:
                    return "[!] 본문 추출에 모두 실패했습니다. 질문이나 키워드를 바꿔보세요."

                all_content = "⎯⎯ 다음 자료 ⎯⎯".join(collected_texts)
                all_content = re.sub(r'!\[.*?\]\([^)]+\)', '', all_content)
                all_content = re.sub(r'\(http[^)]+\)', '', all_content)
                all_content = re.sub(r"\{.*?\}", "", all_content) # { } 있으면 에러남
                all_content = all_content.replace("{", "").replace("}", "")
                all_content = re.sub(r'\[[^\[\]]*\]', '', all_content)
                all_content = re.sub(r'\n+', ' ', all_content)
                answer.append(all_content)
        return "\n".join(answer)
    
    except Exception as e:
        print("[!!EXCEPTION in get_common!!]", type(e), e)
        import traceback; traceback.print_exc()
        raise

############### 창업 아이템 추천 ################
################ 분류 #################
async def get_persona_trend(persona: str, query: str):
    """
    사용자 persona에 맞춰 최적의 트렌드/시장/경쟁사 데이터 취득 함수
    - persona: creator, beautyshop, e_commerce, developer, common
    - return: 텍스트(string)
    """
    # e_commerce는 아마존 트렌딩 상품
    if persona == "ecommerce":
        trend=await get_trending_amazon_products(amazon_url)
        mcp_source="smithery_ai/amazon-product-search"
        return trend,mcp_source
    
    # developer는 한국 앱스토어 신규 인기 앱
    elif persona == "developer":
        smithery_api_key = "056f88d0-aa2e-4ea9-8f2d-382ba74dcb07"
        app_store_url = f"https://server.smithery.ai/@JiantaoFu/appinsightmcp/mcp?api_key={smithery_api_key}&profile=realistic-possum-fgq4Y7"
        trend=await get_trending_new_app(app_store_url)
        mcp_source="smithery_ai/appinsight"
        return trend,mcp_source
    
    # creator는 유튜브 인기 트렌드
    elif persona == "creator":
        smithery_api_key = "056f88d0-aa2e-4ea9-8f2d-382ba74dcb07"
        youtube_url = f"https://server.smithery.ai/@icraft2170/youtube-data-mcp-server/mcp?api_key={smithery_api_key}&profile=realistic-possum-fgq4Y7"
        trend= await get_trending_youtube_videos(youtube_url)
        mcp_source = "smithery_ai/youtube-data-mcp-server"
        return trend,mcp_source
    
    # 나머지(예외)는 common과 동작 동일
    else:
        trend=await get_common(bright_data_url, query)
        mcp_source="smithery_ai/brightdata-search"
        return trend, mcp_source

################################################################################################################################################################
# idea_validation 

def clean_korean_query(text: str) -> str:
    # 1. 한글 조사 제거
    JOSA = r'(을|를|이|가|은|는|도|에|에서|까지|으로|로|와|과|와의|랑|하고|에게|께|보다|마저|조차|처럼|만큼|뿐|밖에|이라도|이나|며|든지|라도|이나마|께서)'
    text = re.sub(rf'\b(\w+){JOSA}\b', r'\1', text)
    text = re.sub(rf'\b{JOSA}\b', '', text)

    # 2. 명령/부탁형 패턴 모두 제거
    pattern = r'''
        (좀)|
        (알려[\s]*줘)|
        (알려[\s]*주세요)|
        (알려[\s]*주[시]*겠어요?)|
        (알려[\s]*주[실]*래요?)|
        (알려[\s]*주[실]*수[\s]*있나요?)|
        (알려[\s]*주셨으면[\s]*좋겠어요?)|
        (알려[\s]*주십시오)|
        (알려[\s]*주셔요)|
        (알려[\s]*주고[\s]*싶어요)|
        (해[\s]*줘)|
        (해[\s]*주세요)|
        (해[주시]*겠어요?)|
        (해[주시]*실래요?)|
        (해[주시]*수[\s]*있나요?)|
        (해[주시]*셨으면[\s]*좋겠어요?)|
        (해[주시]*십시오)|
        (해[주시]*셔요)|
        (해[주시]*고[\s]*싶어요)|
        (말해[\s]*줘)|
        (말해[\s]*주세요)|
        (말해[주시]*겠어요?)|
        (말해[주시]*실래요?)|
        (말해[주시]*수[\s]*있나요?)|
        (말해[주시]*셨으면[\s]*좋겠어요?)|
        (말해[주시]*십시오)|
        (말해[주시]*셔요)|
        (말해[주시]*고[\s]*싶어요)|
        (설명해[\s]*줘)|
        (설명해[\s]*주세요)|
        (설명해[주시]*겠어요?)|
        (설명해[주시]*실래요?)|
        (설명해[주시]*수[\s]*있나요?)|
        (설명해[주시]*셨으면[\s]*좋겠어요?)|
        (설명해[주시]*십시오)|
        (설명해[주시]*셔요)|
        (설명해[주시]*고[\s]*싶어요)
    '''
    text = re.sub(pattern, '', text, flags=re.VERBOSE)

    # 붙임 및 띄어쓰기 변형까지 한 번 더 보정
    text = re.sub(r'(알려 ?줘|알려 ?주세요|알려 ?주[세요]*|알려 ?주실래요|알려 ?주셨으면 좋겠어요?|알려 ?주십시오|알려 ?주셔요|알려 ?주고 싶어요|해 ?줘|해 ?주세요|해 ?주실래요|해 ?주셨으면 좋겠어요?|해 ?주십시오|해 ?주고 싶어요|좀|말해 ?줘|말해 ?주세요|설명해 ?줘|설명해 ?주세요)', '', text)

    # 3. 특수문자, 물음표, 쉼표 등 제거
    text = re.sub(r'[?.,!\"\'\(\)\[\]\{\}]', '', text)

    # 4. 이중공백 및 앞뒤 공백 정리
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

async def get_market_analysis(user_query: str):
    print("[DEBUG] 진입, input:", user_query)
    cleaned_query = clean_korean_query(user_query)
    print("[DEBUG] cleaned_query:", cleaned_query)
    bright_data = await get_common(url=bright_data_url, query=cleaned_query)
    print("[DEBUG] get_common()의 실제 반환값 type:", type(bright_data))
    return bright_data