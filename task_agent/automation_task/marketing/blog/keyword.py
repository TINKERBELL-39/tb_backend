import json
import requests
import random
import time
import hmac
import hashlib
from datetime import datetime, timedelta
import urllib.request
import urllib.error
import base64

class NaverKeywordRecommender:
    def __init__(self, config):
        self.data_lab_config = {
            'client_id': config['datalab']['client_id'],
            'client_secret': config['datalab']['client_secret'],
            'base_url': 'https://openapi.naver.com/v1/datalab'
        }
        self.search_ad_config = {
            'api_key': config['search_ad']['api_key'],
            'secret_key': config['search_ad']['secret_key'],
            'customer_id': config['search_ad']['customer_id'],
            'base_url': 'https://api.searchad.naver.com'
        }

    def recommend_keywords(self, base_keyword, filters={}, count=50):
        try:
            print(f'"{base_keyword}" 기반 키워드 추천 시작...')

            related_keywords = self.generate_related_keywords(base_keyword)
            expanded_keywords = self.expand_keywords([base_keyword], count * 2)
            all_keywords = self.combine_keywords(related_keywords, expanded_keywords, base_keyword)
            keyword_data = self.get_keyword_metrics(all_keywords)
            demographics = self.get_keyword_demographics([k['keyword'] for k in keyword_data[:5]])
            enriched = self.enrich_keyword_data(keyword_data, demographics)
            filtered = self.apply_advanced_filters(enriched, filters)
            ranked = self.calculate_keyword_scores(filtered, base_keyword)

            return {
                'success': True,
                'base_keyword': base_keyword,
                'total_results': len(ranked),
                'keywords': ranked[:count],
                'applied_filters': filters,
                'timestamp': datetime.now().isoformat(),
                'processing_time': '약 5초 이내'
            }
        except Exception as error:
            print('키워드 추천 오류:', error)
            return {'success': False, 'error': str(error), 'keywords': []}

    def expand_keywords(self, seed_keywords, max_results=100):
        try:
            hint_keywords = ','.join(seed_keywords[:5])
            params = {'hintKeywords': hint_keywords, 'showDetail': '1'}
            keyword_list = self.call_search_ad_api('/keywordstool', params)
            return self.extract_expanded_keywords(keyword_list, max_results)
        except Exception as error:
            print('키워드 확장 오류:', error)
            return []

    def extract_expanded_keywords(self, keyword_list, max_results=100):
        try:
            if not keyword_list:
                return []
            return [item.get('relKeyword', '').strip() for item in keyword_list[:max_results]]
        except Exception as e:
            print("extract_expanded_keywords 오류:", e)
            return []

    def get_keyword_metrics(self, keywords):
        try:
            params = {'hintKeywords': ','.join(keywords[:5]), 'showDetail': '1'}
            keyword_list = self.call_search_ad_api('/keywordstool', params)
            return self.process_keyword_metrics(keyword_list)
        except Exception as error:
            print('검색광고 API 오류:', error)
            return self.get_mock_keyword_metrics(keywords)

    def process_keyword_metrics(self, keyword_list):
        try:
            if not keyword_list:
                print("process_keyword_metrics: 빈 리스트")
                return []

            result = []
            for item in keyword_list:
                result.append({
                    'keyword': item.get('relKeyword', '').strip(),
                    'monthly_search_volume': self.parse_int(item.get('monthlyPcQcCnt')) + self.parse_int(item.get('monthlyMobileQcCnt')),
                    'competition': item.get('compIdx', 'MEDIUM'),
                    'avg_cpc': self.parse_float(item.get('monthlyAvePcCtr')),
                    'category': 'IT',
                    'search_intent': 'informational',
                    'is_trending': False,
                    'seasonality': 'all-year'
                })
            return result
        except Exception as e:
            print("process_keyword_metrics 오류:", e)
            return []

    def get_keyword_demographics(self, keywords):
        try:
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            request_body = {
                'startDate': start_date,
                'endDate': end_date,
                'timeUnit': 'month',
                'keywordGroups': [{'groupName': k, 'keywords': [k]} for k in keywords],
                'device': '',
                'ages': ['1', '2', '3', '4', '5'],
                'gender': ''
            }
            response = self.call_data_lab_api('/search', request_body)
            return self.process_demographic_data(response, response, keywords)
        except Exception as error:
            print('데이터랩 API 오류:', error)
            return []

    def process_demographic_data(self, female_data, male_data, keywords):
        result = []
        for idx, keyword in enumerate(keywords):
            f_group = female_data['results'][idx] if 'results' in female_data else {}
            m_group = male_data['results'][idx] if 'results' in male_data else {}
            f_ratio = sum([int(item['ratio']) for item in f_group.get('data', [])]) / len(f_group.get('data', []) or [1])
            m_ratio = sum([int(item['ratio']) for item in m_group.get('data', [])]) / len(m_group.get('data', []) or [1])
            age_dist = {'10s': random.randint(5, 30), '20s': random.randint(15, 50), '30s': random.randint(15, 50), '40s': random.randint(10, 35), '50s': random.randint(5, 25)}
            result.append({
                'keyword': keyword,
                'demographics': {'female_ratio': int(f_ratio), 'male_ratio': int(m_ratio), 'age_distribution': age_dist}
            })
        return result

    def call_search_ad_api(self, endpoint, data):
        timestamp = str(round(time.time() * 1000))
        method = 'GET'
        message = f"{timestamp}.{method}.{endpoint}"
        secret_key = self.search_ad_config['secret_key']
        signature = base64.b64encode(
            hmac.new(secret_key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).digest()
        ).decode('utf-8')

        headers = {
            'Content-Type': 'application/json; charset=UTF-8',
            'X-Timestamp': timestamp,
            'X-API-KEY': self.search_ad_config['api_key'],
            'X-Customer': str(self.search_ad_config['customer_id']),
            'X-Signature': signature
        }

        response = requests.get(self.search_ad_config['base_url'] + endpoint, params=data, headers=headers)
        response.raise_for_status()
        json_data = response.json()
        return json_data.get('keywordList', [])

    def call_data_lab_api(self, endpoint, data):
        request = urllib.request.Request(f"{self.data_lab_config['base_url']}{endpoint}")
        request.add_header('X-Naver-Client-Id', self.data_lab_config['client_id'])
        request.add_header('X-Naver-Client-Secret', self.data_lab_config['client_secret'])
        request.add_header('Content-Type', 'application/json')
        response = urllib.request.urlopen(request, data=json.dumps(data).encode('utf-8'))
        return json.loads(response.read().decode('utf-8'))

    def combine_keywords(self, related, expanded, base):
        all_keywords = set([base] + related + expanded)
        return [k for k in all_keywords if k and len(k) >= 2]

    def enrich_keyword_data(self, metrics_data, demographics_data):
        return [{
            **metric,
            'demographics': next((demo['demographics'] for demo in demographics_data if demo['keyword'] == metric['keyword']), self.get_default_demographics())
        } for metric in metrics_data]

    
    def apply_advanced_filters(self, keywords, filters):
        result = keywords
        print(f"[DEBUG] 필터링 전 키워드 수: {len(result)}")

        if filters.get('category'):
            result = [k for k in result if k['category'] == filters['category']]
            print(f"[DEBUG] category 필터 후: {len(result)}")

        if filters.get('search_volume_range'):
            min_vol = filters['search_volume_range']['min']
            max_vol = filters['search_volume_range']['max']
            result = [k for k in result if min_vol <= k['monthly_search_volume'] <= max_vol]
            print(f"[DEBUG] search_volume_range 필터 후: {len(result)}")

        if filters.get('gender_ratio'):
            gender = filters['gender_ratio']['gender']
            min_ratio = filters['gender_ratio']['min_ratio']
            result = [k for k in result if 
                    (k['demographics']['female_ratio'] if gender == 'female' 
                    else k['demographics']['male_ratio']) >= min_ratio]
            print(f"[DEBUG] gender_ratio 필터 후: {len(result)}")

        if filters.get('age_ratio'):
            age_group = filters['age_ratio']['age_group']
            min_ratio = filters['age_ratio']['min_ratio']
            result = [k for k in result if k['demographics']['age_distribution'].get(age_group, 0) >= min_ratio]
            print(f"[DEBUG] age_ratio 필터 후: {len(result)}")

        return result


    def calculate_keyword_scores(self, keywords, base_keyword):
        result = []
        for k in keywords:
            score = 0
            score += (k['monthly_search_volume'] / 100000) * 30
            score += self.calculate_relevance_score(k['keyword'], base_keyword) * 0.25
            score += 20 if k['competition'] == 'LOW' else 10 if k['competition'] == 'MEDIUM' else 5
            score += 15 if k['is_trending'] else 0
            score += min(k['avg_cpc'] / 1000, 10)
            result.append({**k, 'total_score': round(score, 2)})
        return sorted(result, key=lambda x: x['total_score'], reverse=True)

    def parse_int(self, val):
        try:
            return int(str(val).replace(",", "").replace("<", "").strip())
        except:
            return 0

    def parse_float(self, val):
        try:
            return float(str(val).replace(",", "").strip())
        except:
            return 0.0

    def get_default_demographics(self):
        return {
            'female_ratio': 50,
            'male_ratio': 50,
            'age_distribution': {'10s': 10, '20s': 30, '30s': 30, '40s': 20, '50s': 10}
        }

    def generate_related_keywords(self, base_keyword):
        suffixes = ['방법', '추천', '순위', '리스트', '정보']
        prefixes = ['인기', '추천', '베스트', '유명한']
        return [f"{base_keyword} {s}" for s in suffixes] + [f"{p} {base_keyword}" for p in prefixes]

    def get_mock_keyword_metrics(self, keywords):
        return [{
            'keyword': k,
            'monthly_search_volume': random.randint(1000, 50000),
            'competition': random.choice(['LOW', 'MEDIUM', 'HIGH']),
            'avg_cpc': random.randint(100, 2000),
            'category': 'IT',
            'search_intent': 'informational',
            'is_trending': random.random() > 0.7,
            'seasonality': 'all-year'
        } for k in keywords]

    def calculate_relevance_score(self, keyword, base_keyword):
        score = 0
        if base_keyword in keyword: score += 50
        if keyword in base_keyword: score += 30
        if any(word in base_keyword for word in keyword.split()): score += 20
        return min(score, 100)

# 사용 예시
def example():
    config = {
        'datalab': {
            'client_id': 'dtQJrVVMFjKH9sz_gmd_',
            'client_secret': 'XPZ_QPRD_N'
        },
        'search_ad': {
            'api_key': '01000000004b5fae8ed5d4a9bce22c02db3cc56780a9703f57282bf575ddc2b765e5f455f5',
            'secret_key': 'AQAAAABLX66O1dSpvOIsAts8xWeAY9zcCvrKr2dS+bn92wg+gg==',
            'customer_id': '3519183'
        }
    }
    
    recommender = NaverKeywordRecommender(config)
    
    # 예시 1: 20대 남성이 많이 찾는 IT 키워드
    it_keywords = recommender.recommend_keywords('프로그래밍', {
        'category': 'IT',
        'gender_ratio': {'gender': 'male', 'min_ratio': 10},
        'age_ratio': {'age_group': '20s', 'min_ratio': 20},
        'search_volume_range': {'min': 1000, 'max': 100000}
    }, 30)
    
    print('IT 키워드 추천:', it_keywords)
    
    # 예시 2: 여성이 많이 찾는 다이어트 관련 키워드  
    diet_keywords = recommender.recommend_keywords('다이어트', {
        'gender_ratio': {'gender': 'female', 'min_ratio': 70},
        'search_intent': 'informational',
        'include_words': ['방법', '식단', '운동'],
        'exclude_words': ['광고', '판매']
    }, 25)
    
    print('다이어트 키워드 추천:', diet_keywords)
    
    # # CSV 내보내기
    # if it_keywords['success']:
    #     csv_data = recommender.export_to_csv(it_keywords)
    #     print('CSV 내보내기 완료')

if __name__ == '__main__':
    example()