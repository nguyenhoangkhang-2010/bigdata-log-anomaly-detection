# Frontend (React + Vite + TypeScript)

Giao diện đọc kết quả phát hiện bất thường. Kiểu dữ liệu API sinh từ [`../api/openapi.yaml`](../api/openapi.yaml).

```bash
npm install
npm run dev        # http://localhost:5173  (proxy /api -> http://localhost:8000)
npm run build      # tsc + vite build
npm run gen:api    # sinh lại src/api/schema.d.ts sau khi sửa openapi.yaml (dev/build tự chạy)
```

Muốn trỏ tới backend khác khi build: `VITE_API_URL=https://host npm run build`.

## Hướng thiết kế
Phong cách ấn phẩm: nền giấy ấm, chữ mực, serif (Newsreader) cho tiêu đề và số lớn, mono (IBM Plex Mono) cho nhãn.
Không gradient, không đổ bóng, không bo góc, không thẻ (card) — dùng đường kẻ để chia vùng.
Màu tín hiệu đỏ son **chỉ** dành cho bất thường/lỗi; màu mức log: INFO xám giấy, WARN vàng nghệ, ERROR đỏ son, FATAL mực đen.
Token màu ở `src/styles/tokens.css` (có bản tối). Biểu đồ là SVG tự vẽ, đọc số liệu ở dòng readout phía dưới thay cho tooltip nổi.
