from flask import Flask, render_template, request
import folium
import json
import numpy as np
import os
import requests 

app = Flask(__name__)

# Đảm bảo thư mục Data tồn tại
DATA_FOLDER = 'Data'
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

# Đường dẫn đến file GeoJSON (cần tải file này và đặt vào thư mục Data)
GEOJSON_FILE = os.path.join(DATA_FOLDER, "gadm41_VNM_1.json")

# Biến để lưu trữ lịch sử trò chuyện (trong bộ nhớ, sẽ mất khi server restart)
conversation_history = []

def create_pollution_map(pollution_data_input):
    """Tạo bản đồ ô nhiễm dựa trên dữ liệu đầu vào."""
    try:
        with open(GEOJSON_FILE, "r", encoding="utf-8") as file:
            geojson_data = json.load(file)
    except FileNotFoundError:
        return "Lỗi: Không tìm thấy file GeoJSON. Vui lòng tải file `gadm41_VNM_1.json` và đặt vào thư mục `Data`."
    except json.JSONDecodeError:
        return "Lỗi: File GeoJSON không hợp lệ."

    # pollution_data_input là dictionary có dạng [{ 'Tên Tỉnh': {'AQI': ..., 'CO': ...}, ... },...]
    pollution_data = pollution_data_input 

    # Thêm tooltip và màu sắc
    for feature in geojson_data["features"]:
        province = feature["properties"]["NAME_1"]
        pollution_info = pollution_data.get(province) # Lấy thông tin ô nhiễm cho tỉnh

        if pollution_info:
            tooltip_content = (
                f"<div style='text-align:left; font-size:14px; padding-left:5px;'>"
                f"<b style='text-align:center; display:block; font-size:16px;'>{province}</b><br>"
                f"AQI: <b>{pollution_info.get('AQI', 'Không có dữ liệu')}</b><br>"
                f"CO: {pollution_info.get('CO', 'Không có dữ liệu')} ppm<br>"
                f"SO₂: {pollution_info.get('SO2', 'Không có dữ liệu')} µg/m³<br>"
                f"PM2.5: {pollution_info.get('PM2.5', 'Không có dữ liệu')} µg/m³</div>"
            )
        else:
            tooltip_content = (
                f"<div style='text-align:left; font-size:14px; padding-left:5px;'>"
                f"<b style='text-align:center; display:block; font-size:16px;'>{province}</b></div>"
            )
        feature["properties"]["tooltip_info"] = tooltip_content

    def get_color(aqi):
        if isinstance(aqi, (int, float)):
            if aqi <= 50:
                return "green"
            elif aqi <= 100:
                return "yellow"
            elif aqi <= 150:
                return "orange"
            elif aqi <= 200:
                return "red"
            else:
                return "purple"
        else:
            return "lightgray"

    pollution_map = folium.Map(location=[16.0, 108.0], zoom_start=6, tiles="cartodbpositron")

    folium.GeoJson(
        geojson_data,
        name="Ô nhiễm không khí",
        style_function=lambda feature: {
            "fillColor": get_color(
                # Lấy AQI từ dữ liệu đã xử lý (pollution_data)
                float(pollution_data.get(feature["properties"]["NAME_1"], {}).get("AQI"))
                if pollution_data.get(feature["properties"]["NAME_1"], {}).get("AQI") is not None else None
            ),
            "color": "black",
            "weight": 1,
            "fillOpacity": 0.7,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["tooltip_info"],
            aliases=["Thông tin:"],
            labels=False,
            sticky=True,
            localize=True,
            style=("background-color: rgba(0, 0, 0, 0.85); color: white; font-size: 14px; "
                   "padding: 8px; border-radius: 8px; box-shadow: 2px 2px 10px rgba(0,0,0,0.5);"),
        ),
        highlight_function=lambda feature: {
            "weight": 3,
            "color": "blue",
            "fillOpacity": 0.9,
            "pane": "shadowPane"
        },
    ).add_to(pollution_map)

    # Phần legend_html (tạo node HTML cho chú thích) được thêm vào bản đồ
    legend_html = """
    <div id="legend" style="position: fixed; bottom: 2%; right: 2%; width: 20%; min-width: 140px; max-width: 200px;
                                    background-color: rgba(255, 255, 255, 0.8); z-index:9999; font-size: 1rem;
                                    border-radius: 10px; padding: 1%; box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.3);">
    <b style="font-size: 1.2rem;">📌 Chú thích AQI</b><br><br>
    <div style="display: flex; align-items: center;">
        <span style="background-color:green; width: 1rem; height: 1rem; display:inline-block; border-radius: 5px; margin-right: 0.8rem;"></span>
        <span>Tốt (0-50)</span>
    </div>
    <div style="display: flex; align-items: center; margin-top: 0.4rem;">
        <span style="background-color:yellow; width: 1rem; height: 1rem; display:inline-block; border-radius: 5px; margin-right: 0.8rem;"></span>
        <span>Trung bình (51-100)</span>
    </div>
    <div style="display: flex; align-items: center; margin-top: 0.4rem;">
        <span style="background-color:orange; width: 1rem; height: 1rem; display:inline-block; border-radius: 5px; margin-right: 0.8rem;"></span>
        <span>Kém (101-150)</span>
    </div>
    <div style="display: flex; align-items: center; margin-top: 0.4rem;">
        <span style="background-color:red; width: 1rem; height: 1rem; display:inline-block; border-radius: 5px; margin-right: 0.8rem;"></span>
        <span>Xấu (151-200)</span>
    </div>
    <div style="display: flex; align-items: center; margin-top: 0.4rem;">
        <span style="background-color:purple; width: 1rem; height: 1rem; display:inline-block; border-radius: 5px; margin-right: 0.8rem;"></span>
        <span>Nguy hại (>200)</span>
    </div>
    <div style="display: flex; align-items: center; margin-top: 0.4rem;">
        <span style="background-color:lightgray; width: 1rem; height: 1rem; display:inline-block; border-radius: 5px; margin-right: 0.8rem;"></span>
        <span>Không có dữ liệu</span>
    </div>
    </div>
    <script>
    function resizeLegend() {
        var legend = document.getElementById('legend');
        var windowWidth = window.innerWidth;
        var fontSize = Math.min(Math.max(windowWidth * 0.01, 12), 16); // Font từ 12px đến 16px
        legend.style.fontSize = fontSize + 'px';
    }
    window.addEventListener('resize', resizeLegend);
    window.addEventListener('load', resizeLegend);
    </script>
    """
    pollution_map.get_root().html.add_child(folium.Element(legend_html))


    # Lưu bản đồ vào một file tạm
    temp_map_path = "temp_map.html"
    pollution_map.save(temp_map_path)
    with open(temp_map_path, 'r', encoding='utf-8') as f:
        map_html = f.read()
    os.remove(temp_map_path) # Xóa file tạm sau khi đọc
    return map_html


@app.route("/", methods=["GET", "POST"])
def index():
    global conversation_history
    map_html = ""
    error_message = None
    user_input = None
    pollution_data_for_map = {} # Dictionary để lưu dữ liệu ô nhiễm cho hàm tạo bản đồ

    if request.method == "POST":
        user_input = request.form["pollution_data"]
        conversation_history.append({"sender": "user", "text": user_input})

        # Gửi dữ liệu người dùng nhập (dạng text) trực tiếp đến webhook
        data_to_send = user_input
        webhook_url = "https://complete-truly-silkworm.ngrok-free.app/webhook-test/bba167cb-8a60-4692-a09b-9e4f941c0d6c"
        headers = {'Content-Type': 'text/plain'} # Gửi dạng text/plain

        try:
            # Gửi dữ liệu người dùng nhập dưới dạng text
            response = requests.post(webhook_url, data=data_to_send, headers=headers)
            response.raise_for_status() # Sẽ ném lỗi nếu status code là 4xx hoặc 5xx

            try:
                webhook_response = response.json() # Parse phản hồi JSON

                # Xử lý định dạng JSON từ webhook (object chứa các mảng)
                chatbot_reply = webhook_response.get("reply")# Lấy phản hồi chatbot
                locations = webhook_response.get("location") # Lấy mảng locations
                aqis = webhook_response.get("AQI")           # Lấy mảng AQIs
                cos = webhook_response.get("CO")             # Lấy mảng COs
                so2s = webhook_response.get("SO2")           # Lấy mảng SO2s
                pm25s = webhook_response.get("PM25")         # Lấy mảng PM25s

                if chatbot_reply:
                    conversation_history.append({"sender": "bot", "text": chatbot_reply})

                # Kiểm tra xem các mảng có tồn tại và có cùng độ dài không
                if (isinstance(locations, list) and
                    isinstance(aqis, list) and
                    isinstance(cos, list) and
                    isinstance(so2s, list) and
                    isinstance(pm25s, list) and
                    len(locations) > 0 and # Đảm bảo có ít nhất 1 địa điểm
                    len(locations) == len(aqis) == len(cos) == len(so2s) == len(pm25s)):
                    
                    # Xây dựng dictionary dữ liệu ô nhiễm cho hàm tạo bản đồ
                    pollution_data_for_map = {}
                    for i in range(len(locations)):
                        location_name = locations[i]
                        # Đảm bảo location_name là string và không rỗng
                        if isinstance(location_name, str) and location_name:
                            # Cố gắng chuyển đổi các giá trị sang float, bỏ qua nếu lỗi hoặc giá trị rỗng
                            try:
                                aqi_val = float(aqis[i]) if (aqis[i] is not None and aqis[i] != '') else None
                            except (ValueError, TypeError):
                                aqi_val = None

                            try:
                                co_val = float(cos[i]) if (cos[i] is not None and cos[i] != '') else None
                            except (ValueError, TypeError):
                                co_val = None

                            try:
                                so2_val = float(so2s[i]) if (so2s[i] is not None and so2s[i] != '') else None
                            except (ValueError, TypeError):
                                so2_val = None

                            try:
                                pm25_val = float(pm25s[i]) if (pm25s[i] is not None and pm25s[i] != '') else None
                            except (ValueError, TypeError):
                                pm25_val = None

                            pollution_data_for_map[location_name] = {
                                "AQI": aqi_val,
                                "CO": co_val,
                                "SO2": so2_val,
                                "PM2.5": pm25_val
                            }

                    # Tạo bản đồ nếu có dữ liệu địa điểm hợp lệ được thu thập
                    if pollution_data_for_map:
                        map_html = create_pollution_map(pollution_data_for_map)
                        # Kiểm tra lỗi trả về từ hàm tạo map
                        if isinstance(map_html, str) and "Lỗi:" in map_html:
                             error_message = map_html
                             map_html = ""
                    # else: # Không có dữ liệu map hợp lệ nhưng có thể có reply
                         # pass


                # else: # Phản hồi không chứa mảng dữ liệu map hợp lệ
                     # pass # Có thể chỉ có reply


            except json.JSONDecodeError:
                # Lỗi nếu phản hồi không phải là JSON
                error_message = "Phản hồi từ webhook không phải là định dạng JSON hợp lệ."
            except Exception as e:
                # Lỗi khi xử lý dữ liệu JSON hoặc tạo map
                error_message = f"Đã xảy ra lỗi khi xử lý phản hồi webhook: {e}"
        except requests.exceptions.RequestException as e:
            # Lỗi khi gọi webhook
            error_message = f"Lỗi khi gọi webhook: {e}"
            if hasattr(response, 'text'):
                error_message += f" - Nội dung phản hồi: {response.text}"
        except Exception as e:
            # Lỗi tổng quát khác
            error_message = f"Đã xảy ra lỗi tổng quát: {e}"

    # Khi trang load lần đầu (GET request) hoặc sau POST, render template
    return render_template("index.html", map_html=map_html, error_message=error_message, conversation=conversation_history)


if __name__ == "__main__":
    app.run(debug=True)