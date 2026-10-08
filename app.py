import html
import re
from urllib.parse import quote

import requests
import streamlit as st


st.set_page_config(
    page_title="NAVER 지역검색",
    page_icon=":material/location_on:",
    layout="centered",
)


NAVER_MAP_HTML = """
<div class="map-root" role="img" aria-label="검색 결과 업체 위치를 표시하는 네이버 지도"></div>
<div class="map-status" role="alert"></div>
"""

NAVER_MAP_CSS = """
.map-root {
  width: 100%;
  height: 500px;
  border-radius: 8px;
  overflow: hidden;
}
.map-status {
  display: none;
  box-sizing: border-box;
  width: 100%;
  height: 500px;
  padding: 24px;
  align-items: center;
  justify-content: center;
  text-align: center;
  font: 14px/1.55 system-ui, sans-serif;
  color: var(--st-text-color, #444);
  background: var(--st-secondary-background-color, #f6f7f9);
  border-radius: 8px;
}
"""

NAVER_MAP_JS = """
const componentStates = new WeakMap()

function loadNaverMaps(clientId, onAuthFailure) {
  window.navermap_authFailure = onAuthFailure

  if (window.naver?.maps) return Promise.resolve()
  if (window.__naverMapsSdkPromise) return window.__naverMapsSdkPromise

  window.__naverMapsSdkPromise = new Promise((resolve, reject) => {
    const sdk = document.createElement("script")
    sdk.id = "naver-maps-sdk"
    sdk.src = "https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=" +
      encodeURIComponent(clientId)
    sdk.async = true
    sdk.onload = () => window.naver?.maps
      ? resolve()
      : reject(new Error("NAVER 지도 객체를 찾을 수 없습니다."))
    sdk.onerror = () => reject(new Error("NAVER 지도 SDK 연결에 실패했습니다."))
    document.head.appendChild(sdk)
  })
  return window.__naverMapsSdkPromise
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char])
}

export default function (component) {
  const { data, parentElement } = component
  const mapElement = parentElement.querySelector(".map-root")
  const statusElement = parentElement.querySelector(".map-status")
  if (!mapElement || !statusElement) return

  const showError = (message) => {
    mapElement.style.display = "none"
    statusElement.style.display = "flex"
    statusElement.textContent = message
  }

  const previous = componentStates.get(parentElement)
  if (previous?.map?.destroy) previous.map.destroy()

  mapElement.style.display = "block"
  statusElement.style.display = "none"

  loadNaverMaps(data.clientId, () => showError(
    "지도 인증에 실패했습니다. NAVER Cloud Maps의 Web 서비스 URL과 Client ID를 확인해 주세요."
  )).then(() => {
    const places = data.places || []
    if (!places.length) return

    const map = new naver.maps.Map(mapElement, {
      center: new naver.maps.LatLng(places[0].lat, places[0].lng),
      zoom: 14
    })
    const bounds = new naver.maps.LatLngBounds()

    places.forEach((place) => {
      const position = new naver.maps.LatLng(place.lat, place.lng)
      const marker = new naver.maps.Marker({
        position,
        map,
        title: place.title,
        icon: {
          content: `<div style="background:#03c75a;color:#fff;width:30px;height:30px;` +
            `border-radius:50%;display:flex;align-items:center;justify-content:center;` +
            `font-weight:700;border:2px solid #fff;box-shadow:0 2px 5px rgba(0,0,0,.35)">` +
            `${place.number}</div>`,
          anchor: new naver.maps.Point(15, 15)
        }
      })
      const infoWindow = new naver.maps.InfoWindow({
        content: `<div style="padding:10px;min-width:180px;font-size:13px">` +
          `<b>${place.number}. ${escapeHtml(place.title)}</b><br><br>` +
          `${escapeHtml(place.address)}</div>`
      })
      naver.maps.Event.addListener(marker, "click", () => infoWindow.open(map, marker))
      bounds.extend(position)
    })

    if (places.length > 1) {
      map.fitBounds(bounds, {top: 50, right: 50, bottom: 50, left: 50})
    }
    componentStates.set(parentElement, {map})
  }).catch((error) => showError(error.message))
}
"""

NAVER_MAP_COMPONENT = st.components.v2.component(
    "naver_dynamic_map",
    html=NAVER_MAP_HTML,
    css=NAVER_MAP_CSS,
    js=NAVER_MAP_JS,
    isolate_styles=False,
)

st.title("NAVER 지역검색", anchor=False)
st.caption("지역과 업종을 입력하면 업체와 위치를 지도에서 확인할 수 있습니다.")


class NaverApiError(RuntimeError):
    """사용자에게 안전하게 보여 줄 NAVER API 오류."""


def get_secret(name: str) -> str:
    """필수 secret을 읽되 실제 값은 오류 메시지에 포함하지 않는다."""
    value = st.secrets.get(name)
    if not value:
        raise NaverApiError(
            f"Streamlit Secrets에 {name} 값이 없습니다. 앱 설정에서 키를 등록해 주세요."
        )
    return str(value).strip()


@st.cache_data(ttl=300, max_entries=50, show_spinner=False)
def search_naver_local(query: str) -> list[dict]:
    """NAVER API HUB 지역검색 결과를 최대 5건 반환한다."""
    client_id = get_secret("NAVER_CLIENT_ID")
    client_secret = get_secret("NAVER_CLIENT_SECRET")

    try:
        response = requests.get(
            "https://naverapihub.apigw.ntruss.com/search/v1/local",
            headers={
                "X-NCP-APIGW-API-KEY-ID": client_id,
                "X-NCP-APIGW-API-KEY": client_secret,
            },
            params={
                "query": query,
                "display": 5,
                "start": 1,
                "sort": "random",
                "format": "json",
            },
            timeout=10,
        )
        response.raise_for_status()
    except requests.Timeout as exc:
        raise NaverApiError("NAVER 지역검색 응답 시간이 초과되었습니다.") from exc
    except requests.RequestException as exc:
        status = getattr(exc.response, "status_code", None)
        suffix = f" (HTTP {status})" if status else ""
        raise NaverApiError(f"NAVER 지역검색 요청에 실패했습니다{suffix}.") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise NaverApiError("NAVER 지역검색이 올바른 JSON을 반환하지 않았습니다.") from exc

    items = payload.get("items", [])
    return items if isinstance(items, list) else []


def clean_title(title: str) -> str:
    return html.unescape(re.sub(r"<.*?>", "", title)).strip()


def make_map_data(results: list[dict]) -> list[dict]:
    """지역검색 WGS84 정수 좌표(경·위도 × 10,000,000)를 지도 좌표로 변환한다."""
    places = []
    for number, item in enumerate(results, start=1):
        try:
            longitude = float(item.get("mapx", 0)) / 10_000_000
            latitude = float(item.get("mapy", 0)) / 10_000_000
        except (TypeError, ValueError):
            continue

        if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
            continue

        places.append(
            {
                "number": number,
                "title": clean_title(str(item.get("title", ""))),
                "address": item.get("roadAddress") or item.get("address") or "",
                "lat": latitude,
                "lng": longitude,
            }
        )
    return places


def show_naver_map(places: list[dict]) -> None:
    """NAVER Web Dynamic Map을 Streamlit Custom Component v2로 표시한다."""
    if not places:
        st.info("표시할 수 있는 위치 좌표가 없습니다.", icon=":material/info:")
        return

    try:
        map_client_id = get_secret("NAVER_MAP_CLIENT_ID")
    except NaverApiError as exc:
        st.warning(str(exc), icon=":material/key:")
        return

    NAVER_MAP_COMPONENT(
        data={"clientId": map_client_id, "places": places},
        key="naver-local-map",
        width="stretch",
        height=500,
    )


with st.form("local_search", border=False):
    query = st.text_input(
        "검색어",
        type="search",
        placeholder="예: 노원 정형외과",
    )
    search_button = st.form_submit_button(
        "검색",
        type="primary",
        icon=":material/search:",
        width="stretch",
    )

if search_button:
    normalized_query = query.strip()
    if not normalized_query:
        st.warning("검색어를 입력해 주세요.", icon=":material/warning:")
    else:
        try:
            with st.spinner("NAVER에서 검색 중입니다..."):
                st.session_state["search_results"] = search_naver_local(normalized_query)
                st.session_state["search_query"] = normalized_query
        except NaverApiError as exc:
            st.session_state.pop("search_results", None)
            st.session_state.pop("search_query", None)
            st.error(str(exc), icon=":material/error:")

results = st.session_state.get("search_results")
searched_query = st.session_state.get("search_query", "")

if results is not None:
    if not results:
        st.info("검색 결과가 없습니다.", icon=":material/info:")
    else:
        st.success(f"'{searched_query}' 검색 결과 {len(results)}건", icon=":material/check_circle:")

        st.subheader("검색 결과 지도", anchor=False)
        show_naver_map(make_map_data(results))

        st.divider()
        st.subheader("업체 목록", anchor=False)

        for number, item in enumerate(results, start=1):
            title = clean_title(str(item.get("title", "")))
            category = html.unescape(str(item.get("category", "")))
            address = item.get("roadAddress") or item.get("address") or ""
            business_link = str(item.get("link", "")).strip()
            naver_map_link = "https://map.naver.com/p/search/" + quote(
                f"{title} {address}".strip()
            )

            with st.container(border=True):
                st.subheader(f"{number}. {title}", anchor=False)
                if category:
                    st.text(f"업종: {category}")
                if address:
                    st.text(f"주소: {address}")
                with st.container(horizontal=True):
                    st.link_button(
                        "네이버 지도에서 보기",
                        naver_map_link,
                        icon=":material/map:",
                    )
                    if business_link.startswith(("https://", "http://")):
                        st.link_button(
                            "업체 홈페이지/정보",
                            business_link,
                            icon=":material/open_in_new:",
                        )

st.caption("검색 결과는 NAVER API HUB 지역검색과 NAVER Maps를 이용합니다.")
