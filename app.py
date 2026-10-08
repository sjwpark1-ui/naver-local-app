
import streamlit as st
import streamlit.components.v1 as components
import requests
import re
import html
import json

st.set_page_config(
    page_title="NAVER 지역검색",
    page_icon="📍",
    layout="centered"
)

st.title("📍 NAVER 지역검색")
st.caption("지역과 업종을 입력하면 업체와 위치를 지도에서 확인할 수 있습니다.")


# ==================================================
# NAVER 지역검색
# ==================================================
def search_naver_local(query):

    client_id = st.secrets["NAVER_CLIENT_ID"]
    client_secret = st.secrets["NAVER_CLIENT_SECRET"]

    url = "https://naverapihub.apigw.ntruss.com/search/v1/local"

    headers = {
        "X-NCP-APIGW-API-KEY-ID": client_id,
        "X-NCP-APIGW-API-KEY": client_secret
    }

    params = {
        "query": query,
        "display": 5,
        "start": 1,
        "sort": "random",
        "format": "json"
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=10
    )

    if response.status_code != 200:
        raise Exception(
            f"NAVER API 오류 {response.status_code}: {response.text}"
        )

    return response.json().get("items", [])


# ==================================================
# 업체명 정리
# ==================================================
def clean_title(title):

    title = re.sub(r"<.*?>", "", title)
    title = html.unescape(title)

    return title.strip()


# ==================================================
# 검색 결과를 지도용 데이터로 변환
# ==================================================
def make_map_data(results):

    places = []

    for number, item in enumerate(results, start=1):

        title = clean_title(
            item.get("title", "")
        )

        road_address = item.get(
            "roadAddress",
            ""
        )

        old_address = item.get(
            "address",
            ""
        )

        address = (
            road_address
            if road_address
            else old_address
        )

        try:

            longitude = (
                float(item.get("mapx", 0))
                / 10000000
            )

            latitude = (
                float(item.get("mapy", 0))
                / 10000000
            )

        except:
            continue

        if longitude == 0 or latitude == 0:
            continue

        places.append({
            "number": number,
            "title": title,
            "address": address,
            "lat": latitude,
            "lng": longitude
        })

    return places


# ==================================================
# NAVER Dynamic Map
# ==================================================
def show_naver_map(places):

    if not places:
        return

    map_client_id = st.secrets[
        "NAVER_MAP_CLIENT_ID"
    ]

    places_json = json.dumps(
        places,
        ensure_ascii=False
    )

    center_lat = places[0]["lat"]
    center_lng = places[0]["lng"]

    map_html = f"""
    <!DOCTYPE html>

    <html>

    <head>

        <meta charset="utf-8">

        <script
        type="text/javascript"
        src="https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId={map_client_id}">
        </script>

        <style>

            html, body {{
                margin: 0;
                padding: 0;
                width: 100%;
            }}

            #map {{
                width: 100%;
                height: 500px;
            }}

        </style>

    </head>

    <body>

        <div id="map"></div>

        <script>

        const places = {places_json};

        const map = new naver.maps.Map(
            'map',
            {{
                center: new naver.maps.LatLng(
                    {center_lat},
                    {center_lng}
                ),
                zoom: 14
            }}
        );


        const bounds =
            new naver.maps.LatLngBounds();


        places.forEach(function(place) {{

            const position =
                new naver.maps.LatLng(
                    place.lat,
                    place.lng
                );


            const marker =
                new naver.maps.Marker({{

                    position: position,

                    map: map,

                    title: place.title,

                    icon: {{
                        content:
                        '<div style="' +
                        'background:#03C75A;' +
                        'color:white;' +
                        'width:30px;' +
                        'height:30px;' +
                        'border-radius:50%;' +
                        'display:flex;' +
                        'align-items:center;' +
                        'justify-content:center;' +
                        'font-weight:bold;' +
                        'border:2px solid white;' +
                        'box-shadow:0 2px 5px rgba(0,0,0,0.35);' +
                        '">' +
                        place.number +
                        '</div>',

                        anchor:
                            new naver.maps.Point(
                                15,
                                15
                            )
                    }}

                }});


            const infoWindow =
                new naver.maps.InfoWindow({{

                    content:

                    '<div style="' +
                    'padding:10px;' +
                    'min-width:180px;' +
                    'font-size:13px;' +
                    '">' +

                    '<b>' +
                    place.number +
                    '. ' +
                    place.title +
                    '</b>' +

                    '<br><br>' +

                    place.address +

                    '</div>'

                }});


            naver.maps.Event.addListener(
                marker,
                'click',
                function() {{

                    infoWindow.open(
                        map,
                        marker
                    );

                }}
            );


            bounds.extend(position);

        }});


        if (places.length > 1) {{

            map.fitBounds(
                bounds,
                {{
                    top: 50,
                    right: 50,
                    bottom: 50,
                    left: 50
                }}
            );

        }}

        </script>

    </body>

    </html>
    """

    components.html(
        map_html,
        height=520
    )


# ==================================================
# 검색창
# ==================================================
query = st.text_input(
    "검색어",
    placeholder="예: 노원 정형외과"
)

search_button = st.button(
    "🔍 검색",
    type="primary",
    use_container_width=True
)


# ==================================================
# 검색 실행
# ==================================================
if search_button:

    if not query.strip():

        st.warning(
            "검색어를 입력해주세요."
        )

    else:

        try:

            with st.spinner(
                "NAVER에서 검색 중입니다..."
            ):

                results = search_naver_local(
                    query.strip()
                )

        except Exception as e:

            st.error(
                "검색 중 오류가 발생했습니다."
            )

            st.code(str(e))

            results = []


        if results:

            st.success(
                f"'{query}' 검색 결과 "
                f"{len(results)}건"
            )


            # ----------------------------------
            # 지도 먼저 표시
            # ----------------------------------

            places = make_map_data(
                results
            )

            st.subheader(
                "🗺️ 검색 결과 지도"
            )

            show_naver_map(
                places
            )


            st.divider()

            st.subheader(
                "📋 업체 목록"
            )


            # ----------------------------------
            # 업체 목록
            # ----------------------------------

            for number, item in enumerate(
                results,
                start=1
            ):

                title = clean_title(
                    item.get(
                        "title",
                        ""
                    )
                )

                category = item.get(
                    "category",
                    ""
                )

                road_address = item.get(
                    "roadAddress",
                    ""
                )

                old_address = item.get(
                    "address",
                    ""
                )

                address = (
                    road_address
                    if road_address
                    else old_address
                )

                business_link = item.get(
                    "link",
                    ""
                )


                st.subheader(
                    f"{number}. {title}"
                )


                if category:

                    st.write(
                        f"🏷️ {category}"
                    )


                if address:

                    st.write(
                        f"📍 {address}"
                    )


                if business_link:

                    st.link_button(
                        "🌐 업체 홈페이지/정보",
                        business_link,
                        use_container_width=True
                    )


                st.divider()


        else:

            st.info(
                "검색 결과가 없습니다."
            )


st.caption(
    "검색 결과는 NAVER 지역검색 API와 NAVER Maps를 이용합니다."
)
