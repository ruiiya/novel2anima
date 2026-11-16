# Novel2Moss — Ranh giới dự án độc lập (bắt buộc)

> Phạm vi tệp: hợp đồng kỹ thuật/dữ liệu, không định nghĩa chính sách nội dung. Mọi quyết định nội dung thuộc `docs/novel2moss/CONTENT_POLICY.md`.


## Ranh giới sản phẩm

Novel2Moss là **sản phẩm và mã nguồn độc lập** (*own product and codebase*), không phải fork, bản migration, plugin, adapter, lớp tương thích, tiện ích mở rộng hay biến thể triển khai của bất kỳ dự án chuyển truyện thành ảnh nào trước đây.

**Đầu ra duy nhất gửi model ở V4 là MOSS-Image natural-language positive prompt dạng text.** Logic giữ nguyên nội dung Story/Act/Beat/Storyboard/ShotSpec thuộc Novel2Moss và phải được xây dựng, kiểm thử, quản lý phiên bản ngay tại đây.

## Các phụ thuộc bị cấm

- Không phụ thuộc bắt buộc vào repository, namespace import, đường dẫn đồng cấp, Git submodule, package, executable hoặc tiến trình chạy nền của dự án khác.
- Không dùng chung database, schema, table, migration, catalog, checkpoint, cache, workspace hoặc thư mục sinh artifact với dự án khác.
- Không tự chuyển/import từ schema Story/Shot/Act hoặc quy ước skill của dự án cũ. Nếu sau này bổ sung importer, nó phải là tính năng độc lập, tùy chọn, được người dùng chấp thuận, có ánh xạ và fixture kiểm thử rõ ràng, không phụ thuộc runtime bên ngoài.
- Không giả định Story Engine, persistence, UI, catalog hoặc renderer đã tồn tại chỉ vì dự án khác từng có tính năng tương tự.

## Sở hữu toàn bộ hợp đồng

- Hợp đồng truyện: nguồn, Story, Act, Beat, Event, ShotSpec, chuyển trạng thái, revision và provenance.
- Hợp đồng prompt: ShotSpec → natural-language prompt, kiểm tra văn xuôi và semantic fidelity.
- Hợp đồng QA: phát hiện sai lệch và điều kiện nội dung **trước export**; đối chiếu ảnh sinh ra (nếu có) là quy trình ngoài DB.
- Hợp đồng runtime: export bundle (`natural.prompt.txt`, `prompt.manifest.json`, `fidelity_report.json`), renderer adapter/generation manifest ngoài DB.

Đường dẫn artifact có thể cấu hình, nhưng mặc định phải nằm trong workspace Novel2Moss được chỉ định rõ, trừ khi người dùng chọn thư mục export ngoài. Được dùng chung endpoint render (ví dụ ComfyUI), nhưng đây phải là **tích hợp backend tùy chọn**, không phải phụ thuộc source hoặc database ứng dụng khác.

## Hướng dẫn triển khai

1. Kiểm tra **repository Novel2Moss thật sự** trước khi sửa. Repository rỗng là hợp lệ.
2. Xây dựng/chọn giải pháp theo yêu cầu Novel2Moss. Có thể dùng thư viện phổ biến và tài liệu MOSS công khai; không coi mã nguồn độc quyền của ứng dụng khác là phụ thuộc.
3. Không tự đoán table hay API endpoint. Nếu chưa có tầng ứng dụng, trình bày phạm vi đề xuất và đánh dấu `NOT_IMPLEMENTED`.
4. Duy trì fixture kiểm thử end-to-end không cần repository hay dịch vụ từ xa khác.
5. Ghi rõ capability và renderer ngoài được sử dụng khi chạy. Nếu không có, trả `SKIP`/`BLOCKED` trung thực, không lấy dữ liệu ngầm nơi khác.

## Tiêu chí nghiệm thu tính độc lập

Novel2Moss phải build/test được trên máy sạch chỉ với **repository của chính nó**, các phụ thuộc công khai đã khai báo và renderer tùy chọn. Khi ngắt mọi tích hợp tùy chọn, vẫn phải có thể lập kế hoạch truyện, xuất natural prompt UTF-8, kiểm tra QA cấu trúc và chạy test local (sau khi các chức năng ứng dụng tương ứng được triển khai).
