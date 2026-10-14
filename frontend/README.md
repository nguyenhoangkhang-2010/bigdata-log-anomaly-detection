# Frontend (React + Vite + TypeScript)

Giao diện đọc kết quả phát hiện bất thường. Kiểu dữ liệu API sinh từ [`../api/openapi.yaml`](../api/openapi.yaml).

```bash
npm install
npm run dev        # http://localhost:5173  (proxy /api -> http://localhost:8000)
npm run build      # tsc + vite build
npm run gen:api    # sinh lại src/api/schema.d.ts sau khi sửa openapi.yaml (dev/build tự chạy)
```

Muốn trỏ tới backend khác khi build: `VITE_API_URL=https://host npm run build`.

## Hướng thiết kế: "Áp phích Thụy Sĩ + bút dạ quang"
Nền bê tông xám lạnh, ba màu **phẳng**, tiêu đề đậm bản rộng, số liệu là các mảng màu liền nhau. Không gradient, không đổ bóng, không bo góc, không thẻ (card).

| Thành phần web | Cách làm | File |
|---|---|---|
| Điều hướng | thanh ngang ở đầu trang (không sidebar); mục đang chọn là khối vàng | `components/Shell.tsx`, `styles/layout.css` |
| Dải báo | dải xanh Klein khi dữ liệu là mô phỏng | `Shell.tsx` |
| Số liệu chính | 4 mảng màu tràn hết bề ngang (đen · xanh · vàng · xám) | `pages/Overview.tsx`, `.band` trong `layout.css` |
| Tiêu đề | chữ đậm bản rộng (Archivo 800, độ rộng 125%) + một câu dẫn bên phải | `components/ui.tsx` (`PageTitle`) |
| Nét bút dạ quang | vệt vàng phẳng: mục đang chọn, dòng rê chuột, phần vượt ngưỡng, cụm bất thường, dòng lỗi | `.mark`, `.hl` trong `base.css` |
| Cụm bất thường | dải vàng phía sau biểu đồ + thẻ A1, A2 + danh sách cụm | `components/TimelineChart.tsx` |
| Điểm bất thường | thước đen tới ngưỡng, **phần vàng = phần vượt ngưỡng**, vạch xanh = ngưỡng | `ui.tsx` (`ScoreMeter`) |
| Chân trang | dải đen + chữ LogAD khổng lồ bị cắt ở đáy | `Shell.tsx`, `.foot` |

**Màu** (`src/styles/tokens.css`, có bản tối): đen mực · xanh Klein `#1b34d6` · vàng bút dạ `#f4d200` trên nền xám bê tông `#e2e3df`.
Quy ước nghĩa: **vàng = chú ý/bất thường/FATAL**, **xanh = WARN**, **đen = ERROR**, xám = INFO. Màu mức log lặp lại ở biểu đồ, bảng, dòng log và ký hiệu.

**Chữ:** Archivo (font biến thiên, trục độ rộng 62–125%) cho tiêu đề và nội dung; JetBrains Mono cho mã block, log, số đo nhỏ. Cài qua `@fontsource`, không gọi CDN.

Biểu đồ là SVG tự vẽ; số liệu đọc ở dải đen "đầu đo" phía dưới thay cho tooltip nổi.

## Chức năng gắn với API
- Xuất CSV danh sách bất thường: nút "Xuất CSV" ở trang Bất thường, gọi `GET /api/v1/anomalies/export` cùng bộ lọc đang chọn.
- Lọc theo điểm tối thiểu (`min_score`) ở trang Bất thường; lọc theo khoảng thời gian (`start`/`end`, giờ UTC) ở trang Nhật ký.
- Bộ lọc nằm trên URL nên chia sẻ/refresh vẫn giữ.

## Chưa làm
- Test cho frontend (hiện chỉ có `npm run typecheck` và `npm run build`).
- Thanh cuộn thời gian chung cho mọi trang: cần thêm `start`/`end` vào các endpoint khác trong `openapi.yaml`.
