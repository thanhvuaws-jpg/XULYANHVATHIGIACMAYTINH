"""Nội dung Chương 3 — phân tích hệ thống và xây dựng sản phẩm.

Mọi con số trong tệp này đều lấy từ docs/NHAT_KY_KY_THUAT.md, là số **đo được**
chứ không phải ước lượng. Riêng bảng so sánh mô hình dùng số liệu đo trên ảnh gốc
(Task 12b), không dùng bảng cũ đo trên chip đã căn chỉnh sẵn.
"""

CHUONG_3 = [
    ("p", "Chương này trình bày quá trình xây dựng sản phẩm và toàn bộ số liệu kiểm "
          "chứng. Mục 3.1 đi từ kiến trúc tổng thể xuống từng tầng xử lý, trình bày các "
          "quyết định kỹ thuật kèm số đo chứng minh, và nêu cả những trường hợp phép đo "
          "cho kết quả trái với dự đoán ban đầu. Mục 3.2 giới thiệu giao diện của từng "
          "chức năng."),

    # ---------------------------------------------------------------- 3.1
    ("h2", "3.1. Phân tích hệ thống"),

    ("h3", "3.1.1. Yêu cầu chức năng và phi chức năng"),
    ("p", "Từ mục tiêu ở mục 1.2, hệ thống được xác định gồm các chức năng chính sau:"),
    ("li", "**Đăng ký người dùng**: tạo hồ sơ, chụp hoặc tải lên nhiều ảnh khuôn mặt, "
           "kiểm tra chất lượng từng ảnh và trích đặc trưng lưu vào cơ sở dữ liệu."),
    ("li", "**Nhận diện thời gian thực**: phát hiện và định danh nhiều khuôn mặt trong "
           "luồng video từ webcam, hiển thị tên và độ tin cậy ngay trên khung hình."),
    ("li", "**Nhận diện ảnh tĩnh**: xử lý một ảnh tải lên và trả về kết quả từng khuôn mặt."),
    ("li", "**Điểm danh**: ghi nhận sự có mặt vào buổi học đang diễn ra, tự xác định đúng "
           "giờ hay đi muộn, chống ghi trùng."),
    ("li", "**Chống giả mạo**: chấm điểm thật/giả cho mỗi khuôn mặt và từ chối tấn công "
           "bằng ảnh in hoặc ảnh trên màn hình."),
    ("li", "**Quản trị và báo cáo**: quản lý người, buổi học, xem thống kê, xuất tệp CSV, "
           "xem nhật ký thao tác và sự kiện người lạ."),
    ("p", "Các yêu cầu phi chức năng có ảnh hưởng trực tiếp tới kiến trúc:"),
    ("li", "**Thời gian thực** — tối thiểu 25 khung hình mỗi giây trên máy tính phổ thông."),
    ("li", "**Hoạt động khi mất mạng** — kiosk đặt ở cửa lớp không được ngừng nhận diện "
           "chỉ vì đường truyền chập chờn."),
    ("li", "**Bảo mật** — máy kiosk không được phép tự tạo bản ghi điểm danh; máy chủ "
          "phải là bên xác nhận cuối cùng."),
    ("li", "**Triển khai được** — cài đặt trên máy mới bằng một lệnh, không phụ thuộc "
           "vào môi trường Python có sẵn của máy đó."),

    ("h3", "3.1.2. Kiến trúc tổng thể"),
    ("p", "Hệ thống được tổ chức theo mô hình client–server với bốn thành phần tách bạch:"),
    ("li", "**Thư viện lõi** (engine/) — Python thuần, chứa toàn bộ phần xử lý ảnh và "
           "học máy. Thư viện này **không biết gì** về web, giao diện hay cơ sở dữ liệu."),
    ("li", "**Máy chủ API** (backend/) — FastAPI và SQLAlchemy, cung cấp 23 điểm cuối, "
           "giữ cơ sở dữ liệu và là nơi duy nhất được ghi bản ghi điểm danh."),
    ("li", "**Ứng dụng máy tính** (desktop_app.py) — PySide6, dùng cho máy kiosk và cho "
           "việc đăng ký, chạy engine ngay tại chỗ."),
    ("li", "**Giao diện web** (web/) — React, Vite và Tailwind CSS, dành cho quản trị "
           "và xem báo cáo."),
    ("p", "Lý do tách thư viện lõi ra khỏi máy chủ là điểm thiết kế quan trọng nhất của "
          "hệ thống. Nhờ nó, việc huấn luyện, đo đạc và kiểm thử từng tầng thực hiện được "
          "độc lập; việc đổi mô hình không đụng tới một dòng nào của API; và ứng dụng "
          "kiosk chạy được cả khi máy chủ ngừng hoạt động."),

    ("h3", "3.1.3. Pipeline nhận diện tám tầng"),
    ("p", "Chuỗi xử lý của thư viện lõi gồm tám tầng nối tiếp: **phát hiện → kiểm tra "
          "chất lượng → căn chỉnh → chống giả mạo → trích đặc trưng → tra cứu chỉ mục → "
          "bám vết → bỏ phiếu**. Mỗi tầng được định nghĩa qua một giao diện trừu tượng "
          "với ít nhất hai cách hiện thực để so sánh được với nhau."),
    ("p", "**Lựa chọn bộ phát hiện.** Nhóm cài đặt cả MTCNN và YuNet rồi đo trên cùng "
          "phần cứng. Kết quả ở Bảng 3.1 cho thấy khác biệt quyết định nằm ở kịch bản "
          "nhiều người — đúng kịch bản của lớp học."),
    ("tbl", [["Bộ phát hiện", "Một mặt mỗi ảnh (120 ảnh LFW)", "Khung 1280×720, 12 người"],
             ["YuNet", "4,19 ms · 239 fps", "3,48 ms · 288 fps"],
             ["MTCNN", "28,48 ms · 35 fps", "200,27 ms · 5 fps"],
             ["Tỉ lệ", "nhanh hơn 6,8 lần", "nhanh hơn 57 lần"]]),
    ("cap", "Bảng 3.1. So sánh tốc độ hai bộ phát hiện khuôn mặt"),
    ("p", "Con số đáng chú ý là **57 lần**. Khi số khuôn mặt trong khung hình tăng, MTCNN "
          "chậm đi gần bảy lần (từ 28 ms lên 200 ms) vì mỗi ứng viên phải đi qua hai mạng "
          "phía sau, trong khi YuNet **nhanh hơn một chút** (từ 4,19 ms xuống 3,48 ms) do "
          "ảnh được thu nhỏ về cùng kích thước làm việc. Ở mức 5 khung hình mỗi giây, "
          "MTCNN không dùng được cho nhận diện thời gian thực. Đây chính là nguyên nhân "
          "khiến bản thử nghiệm ban đầu bị giật."),
    ("p", "Về độ chính xác phát hiện, MTCNN nhỉnh hơn trong trường hợp khuôn mặt bị cắt "
          "sát mép ảnh (12,0 so với 11,0 khuôn mặt tìm được trên khung ghép 12 người). "
          "Nhóm chấp nhận đánh đổi này vì tầng bám vết ở cuối pipeline bù lại được: một "
          "khuôn mặt bị sót ở vài khung hình vẫn giữ nguyên danh tính nhờ bỏ phiếu."),

    ("h3", "3.1.4. Cổng chất lượng ảnh và hai lỗi phương pháp đo"),
    ("p", "Tầng kiểm tra chất lượng loại bỏ những khuôn mặt quá mờ, quá tối, quá nhỏ hoặc "
          "quay ngang quá nhiều trước khi trích đặc trưng. Trong quá trình kiểm chứng "
          "tầng này, nhóm phát hiện hai lỗi trong chính cách đo của mình."),
    ("p", "**Lỗi thứ nhất: đo độ nét trên ảnh đã bị biến đổi hình học.** Cách làm ban đầu "
          "là tính phương sai toán tử Laplace trên chip 112×112 sau khi căn chỉnh. Phép "
          "đo này gần như không phản ứng với độ mờ, vì phép biến đổi affine lấy mẫu lại "
          "ảnh và **tự sinh ra tần số cao do răng cưa**, che mất chính thứ cần đo."),
    ("tbl", [["Cách đo (phương sai Laplace chuẩn hoá)", "Ảnh gốc", "Mờ 21 px", "Mờ 31 px", "Độ nhạy"],
             ["Trên chip đã căn chỉnh 112 px", "0,1365", "0,1004", "0,0978", "28 %"],
             ["Trên vùng mặt gốc, thu về 128 px bằng INTER_AREA", "0,0623", "0,0159", "0,0104", "83 %"]]),
    ("cap", "Bảng 3.2. Độ nhạy của phép đo độ nét trước và sau khi sửa"),
    ("p", "Cách sửa là đo trên **vùng mặt ở độ phân giải gốc**, chuẩn hoá kích thước bằng "
          "phép nội suy INTER_AREA vốn có lọc thông thấp đúng cách, rồi chuẩn hoá giá "
          "trị theo phương sai ảnh xám để phép đo bất biến với độ tương phản. Độ nhạy "
          "tăng từ 28 % lên 83 %."),
    ("p", "**Lỗi thứ hai: gộp hai loại góc nghiêng làm một.** Ban đầu tầng này chặn theo "
          "một giá trị \"độ nghiêng\" duy nhất. Nhưng như đã phân tích ở mục 2.2.1, bước "
          "căn chỉnh đã xoay thẳng khuôn mặt trong mặt phẳng ảnh, nên **góc nghiêng đầu "
          "gần như vô hại**, trong khi **góc quay ngang** mới thực sự làm mất thông tin. "
          "Gộp chung khiến hệ thống loại oan ảnh tốt và cho lọt ảnh xấu. Sau khi tách "
          "riêng, ngưỡng đặt ở 30° cho góc quay ngang và nới lên 45° cho góc nghiêng đầu."),
    ("p", "Kết quả kiểm chứng sau khi sửa: ảnh mờ 21 px và 31 px bị loại đúng, ảnh mờ nhẹ "
          "9 px vẫn được chấp nhận, ảnh nghiêng đầu 30° được chấp nhận với điểm 0,92. "
          "Trên 132 ảnh LFW thật, 113 ảnh đạt và 19 ảnh bị loại, tương đương 86 %."),

    ("h3", "3.1.5. Huấn luyện mô hình và ba lỗi khiến quá trình phân kỳ"),
    ("p", "Mô hình trích đặc trưng được huấn luyện bằng hàm mất mát ArcFace trên kiến "
          "trúc MobileFaceNet. Dữ liệu LFW sau khi đi qua bộ phát hiện và cổng chất lượng "
          "còn 5.552 trên 5.823 ảnh, đạt 95,3 %. Sau khi lọc những người có ít hơn bốn "
          "ảnh, còn **582 danh tính**, chia thành bốn tập không giao nhau về danh tính: "
          "349 người huấn luyện, 58 người kiểm định, 116 người kiểm tra và 59 người đóng "
          "vai người lạ."),
    ("p", "Trước khi huấn luyện thành công, quá trình phân kỳ ba lần. Cả ba nguyên nhân "
          "đều được ghi lại vì chúng là bài học kỹ thuật cụ thể:"),
    ("tbl", [["Lần", "Kết quả", "Nguyên nhân", "Cách sửa"],
             ["1", "Mất số ở epoch 1", "Thiếu giai đoạn khởi động tốc độ học",
              "Khởi động tuyến tính trong 200 bước"],
             ["2", "Mất số ở epoch 1", "Số học nửa chính xác bị tràn ở khối thứ 13",
              "Tắt chế độ nửa chính xác"],
             ["3", "Chạy được, 0,8240", "Bộ lập lịch cosin tính đệ quy từ tốc độ học hiện tại",
              "Tự tính lịch theo số bước, bỏ bộ lập lịch"],
             ["4", "0,8827", "—", "—"]]),
    ("cap", "Bảng 3.3. Ba nguyên nhân khiến quá trình huấn luyện phân kỳ"),
    ("p", "Lỗi thứ ba tinh vi nhất và đáng phân tích. Bộ lập lịch cosin của thư viện tính "
          "tốc độ học mới **dựa trên giá trị hiện tại** chứ không dựa trên số bước đã "
          "chạy. Đoạn mã khởi động ghi đè trực tiếp lên tốc độ học đã phá vỡ giả định đó, "
          "khiến giá trị thực tế thấp hơn dự kiến khoảng hai mươi lần. Mô hình vẫn chạy, "
          "vẫn giảm hàm mất mát, chỉ là dừng ở mức 0,8240 mà không có dấu hiệu bất thường "
          "nào. Sau khi tự tính lịch theo số bước, kết quả đạt **0,8827**."),
    ("p", "**Một phát hiện về phần cứng.** Nhóm đo cụ thể tác dụng của chế độ tính toán "
          "nửa chính xác trên card GTX 1650 và thu được kết quả ngược với kỳ vọng thông "
          "thường: **84,8 mili giây mỗi lô ở chế độ đầy đủ, so với 163,2 mili giây ở chế "
          "độ nửa chính xác — chậm hơn hai lần**. Nguyên nhân là card này thuộc dòng "
          "TU117 **không có nhân tensor**, nên phép tính nửa chính xác không được tăng "
          "tốc mà còn tốn thêm chi phí chuyển đổi kiểu dữ liệu. Kết luận rút ra: chế độ "
          "nửa chính xác là khoản lỗ ròng trên card không có nhân tensor, vừa chậm hơn "
          "vừa gây tràn số."),
    ("p", "**Vai trò của biên độ góc ArcFace** cũng được đo trực tiếp. Cùng một mô hình ở "
          "cùng thời điểm, giá trị hàm mất mát khởi điểm là **7,80** khi biên độ bằng 0, "
          "**19,24** khi biên độ bằng 0,2 và **35,45** khi biên độ bằng 0,5. Con số này "
          "giải thích vì sao phải tăng biên độ dần: đặt giá trị cuối ngay từ epoch đầu "
          "khiến bài toán khó gấp bốn lần rưỡi ngay khi trọng số còn ngẫu nhiên."),

    ("h3", "3.1.6. Sửa lỗi rò rỉ danh tính trong đánh giá"),
    ("p", "Cách đánh giá ban đầu chia **ảnh** của cùng một người thành tập đăng ký và tập "
          "truy vấn, khiến mọi danh tính trong tập kiểm tra đều đã xuất hiện lúc huấn "
          "luyện. Như đã phân tích ở mục 2.3.2, đó là rò rỉ dữ liệu. Sau khi chuyển sang "
          "chia theo danh tính, cùng một mô hình FaceNet cho kết quả khác hẳn:"),
    ("tbl", [["Chỉ số", "Cách đánh giá cũ (có rò rỉ)", "Cách đúng (open-set)"],
             ["Diện tích dưới đường ROC", "0,9998", "0,9976"],
             ["Tỉ lệ lỗi cân bằng (EER)", "0,34 %", "1,93 % — xấu hơn 5,7 lần"],
             ["Ngưỡng đề xuất", "0,571", "0,504"],
             ["TAR@FAR = 0,1 %", "không đo được", "0,8233"]]),
    ("cap", "Bảng 3.4. Ảnh hưởng của rò rỉ danh tính lên kết quả đánh giá"),
    ("p", "Con số đáng chú ý nhất là dòng cuối: ở mức chặt chẽ, khi chỉ chấp nhận một "
          "trên một nghìn người lạ lọt qua, hệ thống **bỏ sót 18 % người quen**. Cách "
          "đánh giá cũ hoàn toàn không nhìn thấy điều này, vì nó không có khái niệm "
          "người lạ."),

    ("h3", "3.1.7. Chưng cất tri thức và kết quả so sánh năm mô hình"),
    ("p", "Mô hình huấn luyện từ đầu chỉ đạt mức khiêm tốn do lượng dữ liệu và thời gian "
          "hạn chế. Nhóm áp dụng chưng cất tri thức như trình bày ở mục 2.3.1, dùng "
          "FaceNet làm mô hình thầy. Năm mô hình được đánh giá trên **cùng một tập kiểm "
          "tra gồm 122 người đã đăng ký và 61 người lạ**, không ai xuất hiện lúc huấn luyện."),
    ("tbl", [["Mô hình", "Dữ liệu huấn luyện", "rank-1", "EER", "DIR@1%", "ms", "MB"],
             ["ArcFace từ đầu", "LFW · 349 người", "0,8671", "9,63 %", "0,6756", "5,29", "4,8"],
             ["ArcFace từ đầu", "CASIA · 6.000 người", "0,7563", "9,57 %", "0,2199", "4,16", "4,8"],
             ["Chưng cất", "LFW · 9k ảnh", "0,9082", "5,57 %", "0,5791", "6,63", "4,8"],
             ["Chưng cất", "CASIA+LFW · 112k ảnh", "0,9778", "2,53 %", "0,7199", "4,73", "4,8"],
             ["FaceNet (thầy)", "VGGFace2 · 3,3 triệu ảnh", "0,9842", "1,50 %", "0,8513", "83,70", "107,0"]]),
    ("cap", "Bảng 3.5. So sánh năm mô hình trích đặc trưng trên cùng tập kiểm tra"),
    ("img", "reports/bc_so_sanh_mo_hinh.png"),
    ("cap", "Hình 3.1. So sánh năm mô hình theo bốn tiêu chí: định danh, xác thực, "
            "open-set và chi phí tính toán"),
    ("p", "Ba kết luận rút ra từ bảng trên:"),
    ("li", "**Chưng cất vượt xa huấn luyện từ đầu** ở cùng lượng dữ liệu. Lý do như đã "
           "phân tích ở mục 2.3.1: đích hồi quy 512 chiều mang nhiều thông tin hơn nhãn "
           "một-trong-N, và phương pháp này dùng được cả ảnh không nhãn."),
    ("li", "**Dữ liệu quan trọng hơn thuật toán** trong bài toán này. Vẫn phương pháp "
           "chưng cất, chỉ tăng dữ liệu từ 9 nghìn lên 112 nghìn ảnh đã kéo tỉ lệ đúng "
           "hạng nhất từ 0,908 lên 0,978."),
    ("li", "**Mô hình được chọn đạt gần bằng mô hình thầy với chi phí nhỏ hơn nhiều bậc**: "
           "0,978 so với 0,984 về tỉ lệ đúng hạng nhất, trong khi **nhẹ hơn 22 lần** "
           "(4,8 MB so với 107 MB) và **nhanh hơn 17,7 lần** (4,73 ms so với 83,70 ms)."),
    ("p", "Cấu hình huấn luyện của bốn mô hình do nhóm tự huấn luyện được ghi lại đầy "
          "đủ để chạy lại được:"),
    ("tbl", [["Mô hình", "Epoch", "Tốc độ học", "Tham số ArcFace", "Thời gian", "val_ver"],
             ["ArcFace · LFW", "60", "0,10", "m 0,5 · s 32", "10,5 phút", "0,8600"],
             ["ArcFace · CASIA", "18", "0,10", "m 0,5 · s 64", "128,8 phút", "0,8240"],
             ["Chưng cất · LFW", "30", "0,05", "hồi quy cosine", "17,2 phút", "0,9327"],
             ["Chưng cất · CASIA+LFW", "12", "0,05", "hồi quy cosine", "76,4 phút", "0,9687"]]),
    ("cap", "Bảng 3.6. Cấu hình huấn luyện bốn mô hình do nhóm huấn luyện"),
    ("p", "Mọi mô hình đều dùng chung ảnh vào 112×112, vector ra 512 chiều, lô 64 ảnh, "
          "thuật toán SGD với quán tính 0,9 và suy giảm trọng số 0,0005. Hai mô hình "
          "ArcFace có thêm giai đoạn khởi động tốc độ học và làm mượt nhãn 0,1; hai mô "
          "hình chưng cất không cần vì đích học là vector của mô hình thầy chứ không phải "
          "nhãn phân loại. Cột val_ver là tỉ lệ xác thực đúng trên tập kiểm định gồm "
          "những người **chưa từng xuất hiện lúc huấn luyện**."),
    ("p", "Chênh lệch thời gian giữa hai mô hình chưng cất đáng chú ý: bản LFW chạy 30 "
          "epoch chỉ mất 17,2 phút, còn bản CASIA+LFW chạy 12 epoch đã mất 76,4 phút — "
          "gấp hơn bốn lần cho mỗi epoch, đúng với tỉ lệ tăng dữ liệu từ 9 nghìn lên 112 "
          "nghìn ảnh. Vector đích của mô hình thầy được tính trước một lần rồi lưu lại, "
          "nếu không thì mỗi epoch phải chạy lại mô hình thầy 107 MB trên toàn bộ ảnh."),

    ("p", "Trường hợp mô hình ArcFace huấn luyện từ đầu trên CASIA đáng được nhắc riêng: "
          "nó có tỉ lệ lỗi cân bằng ngang với mô hình huấn luyện trên LFW (9,57 % so với "
          "9,63 %) nhưng chỉ số open-set lại thấp hơn hẳn (0,2199 so với 0,6756). Điều "
          "này minh hoạ đúng nhận xét ở mục 2.3.3: **phân biệt được hai ảnh là một "
          "chuyện, còn cho ra một điểm số đáng tin cậy ở mức tuyệt đối lại là chuyện "
          "khác**. Ngưỡng vận hành đề xuất của mô hình này là 0,977 — sát trần, dấu hiệu "
          "cho thấy mọi vector của nó nằm chen chúc trong một vùng hẹp."),

    ("p", "**Mô hình nào đang chạy trong sản phẩm.** Hệ thống để mặc định là **FaceNet**, "
          "tức mô hình thầy, chứ không phải mô hình chưng cất do nhóm huấn luyện. Lý do "
          "là trên máy có card đồ hoạ, 83,70 mili giây mỗi lượt trích đặc trưng vẫn nằm "
          "trong ngân sách thời gian thực vì chuỗi xử lý chỉ gọi mạng trích đặc trưng mỗi "
          "vài khung trên từng người chứ không gọi mỗi khung, nên phần chính xác hơn "
          "được ưu tiên. Mô hình chưng cất là lựa chọn dành cho máy yếu: đổi trong Bảng "
          "điều khiển rồi dựng lại chỉ mục là chạy được ngay, không phải sửa mã. Cần nói "
          "rõ điều này vì nó ảnh hưởng tới cách đọc kết quả ở Bảng 3.5 — bảng đó so sánh "
          "năng lực các mô hình, không mô tả cấu hình đang chạy."),
    ("p", "Ngoài mạng trích đặc trưng, hệ thống còn dùng bốn mô hình khác, mỗi mô hình "
          "giải một bài toán con:"),
    ("tbl", [["Mô hình", "Vai trò trong hệ thống", "Cỡ", "Nguồn"],
             ["YuNet", "Phát hiện khuôn mặt và 5 điểm mốc để căn chỉnh", "0,23 MB",
              "Có sẵn trong OpenCV"],
             ["MobileFaceNet chưng cất", "Trích đặc trưng — nhóm huấn luyện", "4,8 MB",
              "Nhóm huấn luyện"],
             ["FaceNet (InceptionResnetV1)", "Trích đặc trưng — đang dùng mặc định; đồng "
              "thời là mô hình thầy lúc chưng cất", "107 MB", "Huấn luyện sẵn trên VGGFace2"],
             ["Face Landmarker", "Lưới 478 điểm mốc, dùng để tính EAR cho chống giả mạo",
              "3,8 MB", "MediaPipe"],
             ["Hand Landmarker", "21 điểm mốc bàn tay cho chức năng nhận diện cử chỉ",
              "7,8 MB", "MediaPipe"]]),
    ("cap", "Bảng 3.7. Toàn bộ mô hình có trong hệ thống và vai trò của từng mô hình"),
    ("p", "Mô hình phân tích kết cấu ảnh dùng cho chống giả mạo thụ động vẫn còn trong kho "
          "mã nhưng **đã bị loại khỏi cấu hình mặc định**, vì lý do trình bày ở mục 3.1.9. "
          "Hai mô hình ResNet50 thử nghiệm ở giai đoạn đầu cũng không được dùng: chúng chỉ "
          "đạt tỉ lệ xác thực đúng 0,37 và 0,29, thấp hơn hẳn MobileFaceNet trong khi nặng "
          "gấp hai mươi lần, nên nhóm chuyển hẳn sang kiến trúc nhẹ."),

    ("h3", "3.1.8. Một sai lầm về giao thức đánh giá và cách phát hiện"),
    ("p", "Trong lúc tổng hợp số liệu cho báo cáo, nhóm phát hiện các kết quả open-set "
          "công bố ở những bước trước đó đã bị bóp méo. Nguyên nhân nằm ở **nguồn ảnh "
          "dùng để chấm bài**, không nằm trong mã nguồn."),
    ("p", "Tập kiểm tra ban đầu lấy từ thư mục chứa các chip 112×112 **đã được phát hiện "
          "và căn chỉnh sẵn** từ bước tiền xử lý. Khi chấm bài, chương trình đánh giá lại "
          "chạy bộ phát hiện trên chính chip đó rồi căn chỉnh **lần thứ hai** — cắt một "
          "vùng bên trong ảnh vốn đã chật rồi phóng to lại. Kết quả là một loại ảnh "
          "**không bao giờ xuất hiện lúc chạy thật**, bởi khi vận hành, camera đưa vào "
          "khung hình gốc và chuỗi xử lý chỉ căn chỉnh đúng một lần."),
    ("tbl", [["Mô hình", "DIR@1% trên chip đã căn chỉnh", "DIR@1% trên ảnh gốc", "Chênh lệch"],
             ["ArcFace từ đầu · LFW", "0,2274", "0,6756", "2,97 lần"],
             ["ArcFace từ đầu · CASIA", "0,2107", "0,2199", "1,04 lần"],
             ["Chưng cất · LFW", "0,2308", "0,5791", "2,51 lần"],
             ["Chưng cất · CASIA+LFW", "0,2759", "0,7199", "2,61 lần"],
             ["FaceNet (thầy)", "0,7860", "0,8513", "1,08 lần"]]),
    ("cap", "Bảng 3.8. Ảnh hưởng của nguồn ảnh kiểm tra lên chỉ số open-set"),
    ("p", "Tác hại **không đều giữa các mô hình**, và chính sự không đều đó chỉ ra nguyên "
          "nhân. Mô hình thầy gần như không bị ảnh hưởng vì được huấn luyện trên 3,3 "
          "triệu ảnh rất đa dạng nên chịu được biến dạng lạ. Các mô hình do nhóm huấn "
          "luyện thì bị ảnh hưởng nặng, vì chúng học trên chip đã căn chỉnh và ảnh căn "
          "chỉnh hai lần nằm ngoài phân bố dữ liệu chúng từng thấy."),
    ("p", "Đáng chú ý là tỉ lệ đúng hạng nhất và tỉ lệ lỗi cân bằng gần như không đổi "
          "giữa hai cách chấm; chỉ riêng chỉ số open-set biến động mạnh. Điều này củng cố "
          "thêm nhận định ở mục 2.3.3 rằng open-set là giao thức nhạy cảm nhất và cũng là "
          "giao thức duy nhất phản ánh đúng bài toán điểm danh."),
    ("p", "**Nguyên tắc rút ra:** tập kiểm tra phải đi qua đúng chuỗi xử lý mà hệ thống "
          "thật đi qua — không nhiều hơn cũng không ít hơn một bước nào. Việc dùng lại "
          "thư mục ảnh đã tiền xử lý cho tiện tiết kiệm được vài phút nhưng lặng lẽ tạo "
          "ra một tập kiểm tra không giống điều kiện vận hành. Toàn bộ số liệu trong báo "
          "cáo này đã được đo lại trên ảnh gốc."),

    ("h3", "3.1.9. Tầng chống giả mạo"),
    ("p", "Không có tầng này, mọi độ chính xác đạt được ở các tầng trước đều vô nghĩa về "
          "mặt an ninh: chỉ cần giơ ảnh chân dung trong điện thoại trước camera là điểm "
          "danh hộ được. Nhóm cài đặt bộ phân loại dựa trên **kết cấu ảnh**, trích 12 đặc "
          "trưng vật lý phân biệt khuôn mặt thật với bề mặt phẳng: độ tương phản cục bộ, "
          "phân bố màu, dấu vết vân moiré do lấy mẫu lại màn hình, và độ chói của các "
          "vùng phản xạ."),
    ("p", "**Một cạm bẫy đã gặp phải trong thực tế.** Mô hình đầu tiên đạt ACER chỉ "
          "**0,13 %** — kết quả nhìn qua thì xuất sắc. Nhưng khi kiểm tra riêng với "
          "**ảnh thật bị làm nhiễu nhẹ** (mờ, tối, nén mạnh — đúng những gì webcam giá rẻ "
          "tạo ra), nó từ chối oan tới **56,40 %**. Mô hình đã học một lối tắt: nó không "
          "học phân biệt thật với giả, mà học phân biệt **ảnh sạch với ảnh xấu**, bởi vì "
          "trong dữ liệu huấn luyện mọi ảnh tấn công đều xấu hơn ảnh thật."),
    ("p", "Cách sửa là **khai thác mẫu khó**: bổ sung vào tập huấn luyện những ảnh thật "
          "đã bị làm nhiễu có chủ đích, gán nhãn là thật. Mô hình buộc phải tìm dấu hiệu "
          "khác ngoài chất lượng ảnh. Tỉ lệ từ chối oan giảm từ 56,40 % xuống **9,33 %** "
          "trong khi ACER vẫn giữ ở mức 0,13 %."),
    ("tbl", [["Loại đầu vào", "Điểm thật/giả trung bình", "Tỉ lệ bị chặn"],
             ["Mặt thật", "0,958", "0 %"],
             ["Ảnh in trên giấy", "0,056", "92 %"],
             ["Ảnh trên màn hình", "0,045", "100 %"]]),
    ("cap", "Bảng 3.9. Kết quả tầng chống giả mạo trên tấn công MÔ PHỎNG"),
    ("p", "**Những con số trên hoàn toàn không phản ánh thực tế, và nhóm đã chứng minh "
          "được điều đó bằng đo đạc.** Ứng dụng có sẵn chức năng đo bằng đòn tấn công "
          "thật: ghi 60 khung hình mặt thật trước camera, rồi giơ điện thoại hiển thị ảnh "
          "chân dung và ghi tiếp 60 khung. Kết quả như sau."),
    ("tbl", [["Loại mẫu", "Số khung", "Điểm sống trung bình", "Nhỏ nhất / Lớn nhất"],
             ["Mặt thật", "60", "0,426", "0,01 / 0,94"],
             ["Ảnh trên màn hình điện thoại", "60", "1,000", "1,00 / 1,00"]]),
    ("cap", "Bảng 3.10. Điểm chống giả mạo đo trên tấn công THẬT"),
    ("p", "Điểm sống càng cao nghĩa là hệ thống càng tin đó là người thật. Mô hình chấm "
          "**ảnh trên điện thoại thật hơn cả khuôn mặt thật** — nó không kém, nó **ngược "
          "hoàn toàn**."),
    ("tbl", [["Chỉ số", "Tại ngưỡng hệ thống (0,396)", "Tại ngưỡng tối ưu (0,943)"],
             ["APCER — tấn công lọt qua", "100 %", "100 %"],
             ["BPCER — người thật bị chặn oan", "40 %", "100 %"],
             ["ACER", "70 %", "100 %"]]),
    ("cap", "Bảng 3.11. APCER/BPCER/ACER trên tấn công thật"),
    ("p", "Không một ngưỡng nào cứu được kết quả này: ở mọi điểm cắt, **toàn bộ** đòn tấn "
          "công đều lọt qua. Đây không phải lỗi hiệu chỉnh ngưỡng mà là sai lầm về bản "
          "chất mô hình."),
    ("p", "Phép đo lặp lại lần thứ hai, cùng người và cùng điện thoại nhưng đổi khoảng "
          "cách và ánh sáng, cho bằng chứng trực tiếp về nguyên nhân:"),
    ("tbl", [["Điều kiện đo", "Điểm mặt thật", "Điểm ảnh trên màn hình"],
             ["Lần 1 — ngồi xa, phòng thiếu sáng", "0,426", "1,000"],
             ["Lần 2 — ngồi gần, đủ sáng hơn", "0,995", "1,000"]]),
    ("cap", "Bảng 3.12. Điểm chống giả mạo thay đổi theo điều kiện chụp, không theo sự sống"),
    ("p", "Điểm của khuôn mặt thật **nhảy từ 0,426 lên 0,995** chỉ vì đổi khoảng cách và "
          "ánh sáng, trong khi điểm của đòn tấn công đứng yên ở mức tối đa cả hai lần. "
          "Đại lượng mà mô hình thực sự học được **không phải sự sống mà là chất lượng "
          "ảnh**: nó thưởng cho điều kiện chụp tốt. Màn hình điện thoại luôn sáng, nét và "
          "tương phản cao nên luôn đạt điểm tối đa, còn khuôn mặt thật chỉ đạt điểm cao "
          "khi được chiếu sáng đầy đủ."),
    ("p", "**Nguyên nhân.** Dữ liệu huấn luyện là tấn công mô phỏng, sinh ra bằng cách lấy "
          "ảnh thật rồi làm xấu đi. Mô hình vì thế học đúng một lối tắt: *ảnh xấu là giả, "
          "ảnh sạch là thật*. Thực tế đảo ngược chính xác lối tắt đó — khuôn mặt thật "
          "trong phòng thiếu sáng thì nhiễu và tương phản thấp nên bị coi là \"xấu\", còn "
          "màn hình điện thoại giơ sát camera lại sáng, nét, tương phản cao nên được coi "
          "là \"sạch\"."),
    ("p", "Điều đáng nói là nhóm **đã từng gặp đúng cạm bẫy này** ở giai đoạn huấn luyện, "
          "khi mô hình đầu tiên từ chối oan 56,40 % ảnh thật, và tưởng đã khắc phục xong "
          "bằng kỹ thuật khai thác mẫu khó. Nhưng những mẫu khó đó **cũng do nhóm tự sinh "
          "ra**, nên chúng chỉ vá được lỗ hổng bên trong chính thế giới mô phỏng. Con số "
          "ACER 0,13 % ở Bảng 3.9 vì vậy không có giá trị dự báo nào về thực tế, và được "
          "giữ lại trong báo cáo chỉ để làm đối chứng cho bài học này."),
    ("p", "**Hướng khắc phục.** Hệ thống có sẵn một phương pháp thứ hai không phụ thuộc "
          "kết cấu ảnh: phát hiện **chớp mắt**, đo tỉ lệ khép mí qua nhiều khung hình liên "
          "tiếp. Ảnh tĩnh trên điện thoại không thể chớp mắt, nên về nguyên lý không thể "
          "lách bằng cách chỉnh độ sáng hay độ nét. Khác biệt căn bản nằm ở chỗ kết cấu "
          "ảnh chỉ là dấu hiệu **tương quan**, còn chuyển động mí mắt là dấu hiệu **nhân "
          "quả** của sự sống. Muốn cứu đường phân tích kết cấu thì bắt buộc phải thu dữ "
          "liệu tấn công thật trên nhiều thiết bị và nhiều điều kiện chiếu sáng rồi huấn "
          "luyện lại — không có đường tắt nào đi từ dữ liệu mô phỏng."),

    ("p", "**Kết quả sau khi đổi phương pháp.** Nhóm đo lại bằng đúng quy trình trên, chỉ "
          "thay phân tích kết cấu bằng phát hiện chớp mắt."),
    ("tbl", [["Phương pháp", "Mặt thật", "Màn hình", "APCER", "BPCER", "ACER"],
             ["Kết cấu ảnh", "0,426–0,995", "1,000", "100 %", "0–40 %", "50–70 %"],
             ["Chớp mắt", "1,000", "0,000", "0 %", "0 %", "0 %"]]),
    ("cap", "Bảng 3.13. So sánh hai phương pháp chống giả mạo trên tấn công thật"),
    ("p", "Phân tách tuyệt đối, không một khung hình nào chồng lấn. Điều này khẳng định "
          "nhận định ở trên: kết cấu ảnh chỉ là dấu hiệu **tương quan** với sự sống, và "
          "tương quan ấy đảo chiều ngay khi điều kiện chụp thay đổi; còn chuyển động mí "
          "mắt là dấu hiệu **nhân quả**."),
    ("p", "**Cơ chế phát hiện hoạt động như thế nào.** Mỗi khung hình, bộ dò điểm mốc "
          "khuôn mặt trả về lưới 478 điểm. Sáu điểm quanh mỗi mắt được dùng để tính tỉ lệ "
          "khung hình mắt EAR — tỉ số giữa chiều cao và chiều rộng của mắt:"),
    ("cmd", "EAR = ( |p2-p6| + |p3-p5| ) / ( 2 * |p1-p4| )"),
    ("p", "trong đó p1 và p4 là hai khoé mắt, còn bốn điểm còn lại nằm trên mí trên và mí "
          "dưới. Mắt mở cho EAR lớn, lúc chớp thì tụt xuống rồi bật lại. Giá trị dùng để "
          "quyết định là trung bình EAR của hai mắt."),
    ("p", "Điểm mấu chốt là hệ thống **không bắt trạng thái \"đang nhắm\"** mà bắt trọn "
          "chuỗi **mở → nhắm → mở**. Lý do: một tấm ảnh chụp người đang nhắm mắt cũng cho "
          "EAR thấp, và thấp mãi mãi. Chỉ có chuyển động mí mới sinh ra được chuỗi ba "
          "trạng thái ấy."),
    ("p", "Ngưỡng nhắm/mở **không phải số tuyệt đối** mà tính theo tỉ lệ so với đường nền "
          "EAR của chính khuôn mặt đang xét, lấy bằng phân vị 80 của 90 mẫu gần nhất. Lý "
          "do phải làm vậy đã đo được cụ thể và trình bày ở mục 3.1.16: cùng một đôi mắt "
          "luôn mở, chỉ đổi cỡ khuôn mặt trong khung hình, EAR đo được đã chạy từ 0,112 "
          "tới 0,212 — nghĩa là một ngưỡng cố định lấy từ tài liệu sẽ kết tội oan người "
          "ngồi xa camera."),
    ("p", "Bên cạnh chớp mắt, hệ thống đo thêm một dấu hiệu thứ hai: **mắt có đứng im hay "
          "không**. Mắt người không bao giờ bất động — kể cả giữa hai nhịp chớp vẫn có "
          "rung mắt, đảo mắt và nheo nhẹ theo ánh sáng, nên EAR luôn dao động. Một tấm "
          "ảnh thì EAR gần như là hằng số. Hệ số biến thiên của EAR trên 45 khung gần "
          "nhất dưới 0,020 được coi là ảnh tĩnh. Dấu hiệu này bắt được ảnh in và ảnh trên "
          "màn hình **trước khi** người dùng kịp chớp mắt, nên rút ngắn thời gian chờ."),
    ("tbl", [["Tham số", "Giá trị", "Ý nghĩa"],
             ["Tỉ lệ nhắm", "0,72 × đường nền", "EAR tụt dưới mức này coi là đang nhắm"],
             ["Tỉ lệ mở", "0,85 × đường nền", "Bật lại trên mức này là hoàn tất một lần chớp"],
             ["EAR sàn", "0,06", "Dưới mức này coi là đo hỏng, không phải mắt nhắm"],
             ["Số mẫu tối thiểu", "90 khung", "Chưa đủ thì trả \"chưa đo được\", không kết tội"],
             ["Hiệu lực một lần chớp", "15 giây", "Quá hạn phải chớp lại"],
             ["Hạn sống của ô theo dõi", "0,6 giây", "Mất mặt quá hạn thì xoá cả lịch sử chớp"],
             ["Ngưỡng mắt đứng im", "0,020", "Hệ số biến thiên EAR trên 45 khung"],
             ["Thời gian chờ", "3 – 12 giây", "Nội suy theo mức chuyển động đo được"]]),
    ("cap", "Bảng 3.14. Tham số của bộ phát hiện chớp mắt"),
    ("p", "Hai chi tiết còn lại đều sinh ra từ lỗi gặp khi người dùng thật thử phá hệ "
          "thống, trình bày kỹ ở mục 3.1.16. Thứ nhất, bằng chứng chớp mắt gắn vào **một "
          "khuôn mặt được theo dõi liên tục**, không gắn vào một vị trí trên màn hình: ô "
          "theo dõi không thấy mặt quá 0,6 giây là bị xoá cùng toàn bộ lịch sử, chặn đòn "
          "chớp mắt xong hạ mặt xuống rồi giơ ảnh vào đúng chỗ vừa rời đi. Thứ hai, hệ "
          "thống phân biệt rõ **\"chưa đo được\"** với **\"là giả\"**: khi số mẫu chưa đủ, "
          "điểm sống trả về giá trị âm quy ước và giao diện hiển thị khung vàng kèm chữ "
          "\"đang kiểm tra\" chứ không kết tội giả mạo."),

    ("p", "**Một hệ quả kiến trúc quan trọng.** Phát hiện chớp mắt là tín hiệu theo thời "
          "gian, đòi hỏi cả một chuỗi khung hình. Máy chủ chỉ nhận **một tấm ảnh** mỗi "
          "lần điểm danh nên về nguyên tắc không thể tự kiểm tra liveness — đây là giới "
          "hạn của giao thức, không phải của thư viện. Tầng chống giả mạo vì vậy được đặt "
          "tại **máy kiosk**, nơi có luồng video, và phía máy chủ chủ động tắt."),
    ("p", "Đánh đổi cần nêu rõ: danh tính vẫn do máy chủ quyết định vì nó tự nhận diện lại "
          "ảnh gửi lên, nên một máy kiosk bị chiếm quyền **không** giả mạo được danh tính. "
          "Nhưng bước kiểm tra chống giả mạo thì máy kiosk đó có thể bỏ qua. Mô hình tin "
          "cậy của tầng chống giả mạo do đó yếu hơn tầng nhận diện. Muốn khoá lại thì "
          "kiosk phải gửi một chuỗi khung hình ngắn để máy chủ tự đo, tốn băng thông hơn "
          "nhiều và nằm ngoài phạm vi đề tài này."),
    ("p", "**Giới hạn của chính kết quả này.** Con số ACER 0 % đạt được trên **một phiên "
          "đo, một người và một thiết bị tấn công**. Đó là bằng chứng đủ để chọn phương "
          "pháp, nhưng chưa đủ để tuyên bố hệ thống an toàn. Cần đo thêm trên nhiều người, "
          "nhiều loại màn hình và cả ảnh in. Đặc biệt cần kiểm tra hai điểm yếu đã biết "
          "của phát hiện chớp mắt: **video quay sẵn có người chớp mắt** — một đòn tấn công "
          "cao cấp hơn ảnh tĩnh — và **người đeo kính dày** làm mờ dấu hiệu mí mắt."),

    ("h3", "3.1.10. Thí nghiệm cắt bỏ — đóng góp thật của từng thành phần"),
    ("p", "Khẳng định hệ thống \"có căn chỉnh, có cổng chất lượng, có bám vết\" thì dễ. "
          "Chứng minh từng thành phần đáng tồn tại thì phải tắt nó đi rồi đo lại trên "
          "cùng tập kiểm tra và cùng mô hình. Chênh lệch chính là đóng góp thật."),
    ("img", "reports/bc_ablation.png"),
    ("cap", "Hình 3.2. Kết quả thí nghiệm cắt bỏ ba thành phần chính"),
    ("p", "**Căn chỉnh khuôn mặt là thành phần đóng góp lớn nhất toàn hệ thống.** Thay "
          "phép căn chỉnh theo năm điểm mốc bằng cách chỉ cắt hộp bao rồi thu nhỏ, tỉ lệ "
          "đúng hạng nhất tụt từ 0,9778 xuống **0,8829**, và chỉ số open-set tụt từ "
          "0,7199 xuống **0,5538**. Khoảng cách điểm giữa người quen và người lạ co lại "
          "từ 0,255 xuống 0,184, khiến việc chọn ngưỡng trở nên khó hơn nhiều."),
    ("p", "**Cổng chất lượng: một kết quả buộc nhóm phải xét lại chính thiết kế của "
          "mình.** Ngưỡng độ nét ban đầu đặt ở 0,025, hiệu chỉnh theo ảnh của bộ LFW. Ở "
          "ngưỡng đó, thí nghiệm cắt bỏ cho thấy cổng làm tỉ lệ đúng hạng nhất **giảm** "
          "1,1 điểm nhưng chỉ số open-set **tăng** 5,1 điểm — một đánh đổi có vẻ đáng giá, "
          "vì điểm danh là bài toán open-set."),
    ("p", "Nhưng khi đưa hệ thống cho người dùng thật chạy thử trên webcam, con số ấy lộ "
          "ra mặt khác: trong 12 ảnh đăng ký, **chỉ 4 ảnh qua được cổng**, và nhận diện "
          "trực tiếp liên tục báo không nhận ra. Kiểm tra kỹ thì hai ảnh **bị loại vì "
          "\"ảnh mờ\"** lại vẫn nhận đúng người với độ tương đồng **0,9383** và **0,7751** "
          "— thừa xa ngưỡng chấp nhận 0,55, và hai ảnh đó không nằm trong tập đăng ký nên "
          "đây không phải kết quả vòng vo. Cổng đang loại bỏ chính những ảnh mà hệ thống "
          "thừa sức nhận ra."),
    ("p", "Nhóm đo lại quan hệ giữa độ nét và khả năng nhận diện trên 632 ảnh gốc để chọn "
          "ngưỡng bằng số liệu thay vì bằng cảm tính."),
    ("tbl", [["Khoảng độ nét", "Số ảnh", "rank-1"],
             ["0,000 – 0,010", "8", "0,875"],
             ["0,010 – 0,015", "15", "1,000"],
             ["0,015 – 0,020", "64", "0,953"],
             ["0,020 – 0,025", "67", "0,970"],
             ["0,025 – 0,035", "151", "0,980"],
             ["trên 0,060", "115", "0,991"]]),
    ("cap", "Bảng 3.15. Quan hệ giữa độ nét ảnh và tỉ lệ nhận diện đúng"),
    ("p", "Độ chính xác **chỉ sụt thật sự dưới 0,010**. Ngưỡng cũ 0,025 loại 146 trên 632 "
          "ảnh, tức 23 %, trong khi những ảnh ấy vẫn nhận đúng tới khoảng 96 %. Ngưỡng "
          "được hạ xuống **0,010** và thí nghiệm cắt bỏ chạy lại:"),
    ("tbl", [["", "Ngưỡng 0,025", "Ngưỡng 0,010"],
             ["Ảnh đăng ký bị loại", "29,5 %", "1,9 %"],
             ["Người không đăng ký nổi", "7 trên 122", "0 trên 122"],
             ["rank-1 so với không lọc", "−0,0111", "±0,0000"],
             ["DIR@FAR=1% so với không lọc", "+0,0508", "±0,0000"]]),
    ("cap", "Bảng 3.16. Cổng chất lượng ở hai ngưỡng khác nhau"),
    ("p", "Đây là kết luận đáng ghi nhận nhất của thí nghiệm này: **toàn bộ lợi ích 5,1 "
          "điểm open-set mà cổng chất lượng từng mang lại đều đến từ việc nó loại rất "
          "gắt.** Nới ngưỡng vừa đủ để hệ thống dùng được ngoài đời thì lợi ích đo được "
          "biến mất hoàn toàn."),
    ("p", "Vậy có nên bỏ hẳn cổng chất lượng? Nhóm giữ lại, nhưng mô tả đúng vai trò của "
          "nó thay vì thổi phồng. Thứ nhất, nó vẫn chặn **phần đuôi thật sự hỏng**: dưới "
          "0,010 tỉ lệ đúng tụt còn 0,875, và một ảnh mẫu hỏng lọt vào tập đăng ký sẽ gây "
          "nhận nhầm về sau rất khó truy nguyên. Phần đuôi này hiếm trên LFW nên không "
          "hiện ra trong chỉ số tổng hợp, nhưng nó tồn tại. Thứ hai, và quan trọng hơn, "
          "giá trị lớn nhất của cổng là **phản hồi hướng dẫn** chứ không phải lọc bỏ: nó "
          "cho người dùng biết cần giữ yên máy, nhìn thẳng hay lại gần camera."),
    ("p", "Nhận xét cuối cùng liên quan tới trải nghiệm người dùng. Ban đầu, khi một khung "
          "hình trượt cổng, hệ thống chỉ hiển thị \"Chưa nhận ra\" — câu ít hữu ích nhất "
          "có thể đưa ra, bởi chương trình **biết chính xác** vấn đề nằm ở đâu nhưng lại "
          "bỏ thông tin đó đi ngay sau khi kiểm tra. Phần hiển thị đã được sửa để nêu rõ "
          "lý do ngay dưới khung khuôn mặt."),
    ("p", "**Bám vết và bỏ phiếu không làm hệ thống thông minh hơn nhiều, mà làm nó "
          "ngừng trông như đang hỏng.** Độ chính xác chỉ tăng 2,1 điểm (từ 0,9467 lên "
          "0,9672), nhưng số lần nhãn nhấp nháy giảm từ **7,0 xuống 0,9 trên mỗi 100 "
          "khung hình — giảm 87 %**. Không có bỏ phiếu, cứ khoảng nửa giây tên hiển thị "
          "lại đổi một lần dù phần lớn thời gian hệ thống đoán đúng. Cái giá là phải chờ "
          "trung bình **5,1 khung hình**, tương đương 0,2 giây ở tốc độ 25 khung hình mỗi "
          "giây, mới dám chốt danh tính."),

    ("h3", "3.1.11. Thiết kế cơ sở dữ liệu và nghiệp vụ điểm danh"),
    ("p", "Cơ sở dữ liệu gồm chín bảng: người dùng hệ thống, người được nhận diện, vector "
          "đặc trưng, ảnh đăng ký, buổi học, bản ghi điểm danh, sự kiện người lạ, thiết "
          "bị kiosk và nhật ký thao tác."),
    ("p", "Hai quyết định thiết kế đáng nêu. Thứ nhất, bảng vector đặc trưng có thêm cột "
          "**định danh mô hình**. Vector do hai mô hình khác nhau sinh ra nằm trong hai "
          "không gian khác nhau; trộn chúng vào một chỉ mục sẽ cho kết quả sai một cách "
          "âm thầm, không báo lỗi. Cột này cho phép hệ thống chỉ nạp đúng vector tương "
          "thích và cảnh báo khi phát hiện vector của mô hình cũ."),
    ("p", "Thứ hai, bảng điểm danh có **ràng buộc duy nhất** trên bộ ba (người, buổi học, "
          "ngày). Đây là chốt chặn cuối cùng của cơ chế chống ghi trùng ba tầng:"),
    ("tbl", [["Tầng", "Cơ chế", "Ngăn được gì"],
             ["Bám vết", "Mỗi vết chỉ phát đúng một sự kiện", "Đứng 30 giây trước camera vẫn chỉ tạo 1 sự kiện"],
             ["Kiosk", "Nhớ 60 giây gần nhất theo tên", "Lưu lượng mạng vô ích"],
             ["Cơ sở dữ liệu", "Ràng buộc duy nhất theo ngày", "Mọi trường hợp còn lại, kể cả sau khi đồng bộ hàng đợi"]]),
    ("cap", "Bảng 3.17. Ba tầng chống ghi trùng bản ghi điểm danh"),
    ("p", "Ba tầng độc lập nhau có chủ đích: hai tầng trên là tối ưu hiệu năng, tầng dưới "
          "cùng mới là chốt chặn đúng nghĩa, vẫn giữ được tính đúng đắn ngay cả khi hai "
          "tầng trên bị lỗi."),
    ("p", "**Một giới hạn cần nêu rõ: mỗi lần điểm danh chỉ ghi được một người.** Khi có "
          "nhiều khuôn mặt trong khung hình, máy chủ chọn khuôn mặt **lớn nhất** — tức "
          "người đứng gần camera nhất — và bỏ qua những người còn lại. Các tầng phát "
          "hiện, bám vết và hiển thị đều xử lý được nhiều người cùng lúc, chỉ riêng bước "
          "ghi sổ là một-người-một-lượt."),
    ("p", "Đây là lựa chọn có chủ đích chứ không phải thiếu sót kỹ thuật. Ghi tất cả "
          "khuôn mặt nhận ra được sẽ khiến người **đi ngang qua phía sau** kiosk cũng bị "
          "điểm danh — một kiểu điểm danh hộ ngoài ý muốn mà không ai kiểm soát được. Với "
          "kiosk đặt ở cửa lớp, nơi người ta đi qua lần lượt, ràng buộc một-người-một-lượt "
          "vừa an toàn hơn vừa đúng với cách sử dụng thực tế."),

    ("h3", "3.1.12. Kiosk và khả năng hoạt động khi mất mạng"),
    ("p", "Máy kiosk chạy engine ngay tại chỗ chứ không gửi từng khung hình lên máy chủ, "
          "vì ba lý do: phản hồi tức thì trong vài chục mili giây thay vì chờ một vòng "
          "mạng; vẫn nhận diện được khi mất mạng; và không thể gửi 30 khung hình mỗi giây "
          "lên máy chủ khi có nhiều kiosk cùng hoạt động."),
    ("p", "Tuy vậy **máy chủ vẫn là bên xác nhận cuối cùng**: kiosk gửi ảnh chụp lên, máy "
          "chủ tự nhận diện lại rồi mới ghi bản ghi. Kiosk chỉ đề xuất chứ không tự quyết, "
          "nên một máy kiosk bị chiếm quyền cũng không tạo được bản ghi giả."),
    ("p", "Khi mất mạng, ảnh và siêu dữ liệu được ghi xuống đĩa và một luồng nền thử gửi "
          "lại theo chu kỳ 30 giây. Người đứng trước camera vẫn thấy thông báo đã ghi "
          "nhận, vì bản ghi chắc chắn sẽ tới nơi. Kết quả kiểm thử: 4 bản ghi xếp hàng "
          "khi mất mạng được gửi đủ 4 khi mạng trở lại, và cơ chế chống ghi trùng vẫn "
          "hiệu lực — 4 bản ghi cùng người cùng ngày chỉ tạo thêm 0 dòng trong sổ."),

    ("h3", "3.1.13. Đóng gói và triển khai"),
    ("p", "Toàn bộ hệ thống được đóng gói bằng Docker và khởi động bằng một lệnh. Kiến "
          "trúc triển khai gồm hai vùng chứa: một chạy nginx phục vụ giao diện web và "
          "chuyển tiếp lời gọi API, một chạy máy chủ API cùng engine. **Chỉ vùng chứa "
          "nginx mở cổng ra ngoài**; máy chủ API chỉ nói chuyện trong mạng nội bộ nên "
          "không thể bị gọi trực tiếp từ bên ngoài."),
    ("p", "Quyết định kỹ thuật đáng nêu nhất là **không cài PyTorch vào ảnh triển khai**. "
          "Mô hình đã được xuất sang định dạng ONNX nên lúc chạy chỉ cần ONNX Runtime. "
          "Nhóm dựng thêm một ảnh đối chứng có cài PyTorch để đo chính xác khoản chênh lệch:"),
    ("tbl", [["Ảnh triển khai", "Dung lượng", "Thời gian trích đặc trưng mỗi khuôn mặt"],
             ["Có PyTorch (bản CPU)", "1,92 GB", "9,1 ms"],
             ["Chỉ ONNX Runtime", "941 MB", "4,7 ms"],
             ["Giao diện web (nginx)", "74,4 MB", "—"]]),
    ("cap", "Bảng 3.18. Dung lượng ảnh triển khai đo được"),
    ("p", "Việc xuất mô hình sang ONNX vì vậy không phải một bước làm cho đẹp mà là một "
          "phần của kiến trúc triển khai: nó quyết định đồng thời dung lượng cần tải về "
          "và tốc độ xử lý mỗi khuôn mặt."),
    ("p", "Trong quá trình đóng gói, bốn lỗi được phát hiện mà **không bộ kiểm thử mã "
          "nguồn nào bắt được**, vì chúng chỉ tồn tại ở môi trường đã đóng gói:"),
    ("li", "**Vùng chứa chết ngay khi khởi động.** Một dòng khai báo nhập khẩu ở đầu tệp "
           "khởi tạo gói kéo theo PyTorch, vô hiệu hoá toàn bộ thiết kế nạp trì hoãn. "
           "Nguy hiểm ở chỗ máy phát triển nào cũng có PyTorch nên lỗi chỉ lộ ra lúc "
           "triển khai."),
    ("li", "**API giới thiệu mô hình mà chính nó không chạy được** — danh sách mô hình "
           "liệt kê cứng mô hình chạy bằng PyTorch."),
    ("li", "**Ảnh triển khai phình thêm 380 MB một cách vô hình.** Các tầng của Docker "
           "chỉ cộng dồn, nên xoá tệp ở tầng sau không hề gỡ bỏ dữ liệu ở tầng trước."),
    ("li", "**Vùng chứa khoẻ nhưng bị gắn nhãn hỏng** — 94 lần kiểm tra thất bại liên "
           "tiếp trong khi trang web phục vụ bình thường, do tên localhost bên trong "
           "vùng chứa phân giải ra địa chỉ IPv6 trong khi nginx chỉ lắng nghe trên IPv4."),
    ("p", "Bốn lỗi này là lý do nhóm bổ sung hai bộ kiểm thử gọi qua giao thức HTTP vào "
          "**hệ thống đã triển khai thật** thay vì chỉ gọi vào mã nguồn."),

    ("h3", "3.1.14. Cập nhật thời gian thực cho giao diện web"),
    ("p", "Ban đầu giao diện web chỉ biết có bản ghi mới khi người dùng tự bấm tải lại "
          "trang. Với một màn hình treo ở phòng giáo vụ để theo dõi lớp đang điểm danh thì "
          "điều đó vô dụng: thông tin đúng đã nằm trong cơ sở dữ liệu nhưng không ai thấy."),
    ("p", "Giải pháp là để **máy chủ chủ động đẩy** qua WebSocket thay vì để trình duyệt "
          "hỏi lại theo chu kỳ. Cách hỏi lại tạo lưu lượng liên tục kể cả khi cả buổi "
          "không ai điểm danh, và vẫn trễ vài giây; cách đẩy thì không có bản ghi mới là "
          "không có gói tin nào."),
    ("p", "Ba chi tiết quyết định việc kênh này chạy được lâu dài. Thứ nhất, thẻ đăng "
          "nhập đi trong **thân gói tin** chứ không nằm trên đường dẫn — chuỗi truy vấn "
          "bị ghi vào nhật ký máy chủ, nhật ký proxy và lịch sử trình duyệt. Thứ hai, "
          "nginx phải được cấu hình cho phép nâng cấp giao thức; thiếu bước này thì kết "
          "nối im lặng không mở được **mà không có thông báo lỗi nào**. Thứ ba, việc nối "
          "lại phải có giãn cách tăng dần, nếu không mọi trình duyệt đang mở sẽ cùng dội "
          "vào máy chủ đúng lúc nó vừa khởi động lại và còn đang nạp mô hình."),

    ("h3", "3.1.15. Kiểm thử"),
    ("p", "Hệ thống có bảy bộ kiểm thử tự động với tổng cộng **85 phép thử, tất cả đều đạt**:"),
    ("tbl", [["Bộ kiểm thử", "Số phép thử", "Phạm vi kiểm chứng"],
             ["Kiểm tra không phụ thuộc PyTorch", "6", "Không có khai báo nhập khẩu nào kéo PyTorch vào"],
             ["Kiểm thử luồng nghiệp vụ", "25", "Phân quyền, đăng ký, nhận diện, điểm danh, báo cáo"],
             ["Kiểm thử kiosk", "11", "Hàng đợi ngoại tuyến, đồng bộ, chống ghi trùng"],
             ["Kiểm thử khói hệ thống triển khai", "20", "Ảnh Docker, nginx, biến môi trường, lưu trữ"],
             ["Kiểm thử kênh thời gian thực", "5", "WebSocket qua nginx, xác thực, đẩy sự kiện"],
             ["Kiểm thử vết chờ xác minh", "6", "Chỗ nối giữa nhận diện và chống giả mạo"],
             ["Kiểm thử số liệu tổng hợp", "12", "Đơn vị đếm và các đẳng thức giữa các ô số liệu"]]),
    ("cap", "Bảng 3.19. Bảy bộ kiểm thử tự động của hệ thống"),
    ("p", "Hai bộ cuối gọi qua HTTP vào hệ thống đã triển khai, trong đó có phép thử xác "
          "nhận cổng của máy chủ API **không** truy cập được từ bên ngoài. Trong quá "
          "trình chạy lại toàn bộ, nhóm còn phát hiện một lỗi của chính bộ kiểm thử: nó "
          "tạo buổi học kéo dài từ thời điểm hiện tại tới hai giờ sau, nên khi chạy sau "
          "22 giờ thì giờ kết thúc rơi sang ngày hôm sau và bị máy chủ từ chối đúng luật. "
          "Bộ kiểm thử chạy tốt suốt cả ngày và chỉ hỏng về khuya — loại lỗi dễ khiến "
          "người ta nghi oan cho mã nguồn."),

]

# Mở đầu mục 3.2 — tách riêng khỏi CHUONG_3 vì các mục 3.1.16 và 3.1.17
# (ở noidung_c3b.py) phải được chèn TRƯỚC tiêu đề 3.2. Gộp chung thì phần
# người dùng thật rơi vào giữa mục giao diện, đúng lỗi đã gặp ở bản dựng trước.
MO_DAU_32 = [
    ("h2", "3.2. Xây dựng giao diện sản phẩm"),
    ("p", "Hệ thống có hai giao diện phục vụ hai nhóm người dùng khác nhau. Ứng dụng máy "
          "tính dành cho máy kiosk đặt tại lớp và cho công việc đăng ký, cần truy cập "
          "camera và phản hồi tức thì. Giao diện web dành cho giảng viên và quản trị "
          "viên, cần truy cập được từ mọi máy trong mạng mà không phải cài đặt gì."),
    ("p", "Cả hai giao diện dùng chung một bảng màu và một bộ biểu tượng vector, tránh "
          "dùng ký tự cảm xúc làm biểu tượng chức năng để giữ vẻ ngoài đồng nhất trên "
          "mọi hệ điều hành."),
]

# Các mục giao diện. Phần tử thứ ba là tên tệp ảnh trong report/anh_app/.
# Thiếu tệp thì bộ dựng giữ nguyên dòng chỗ trống — không làm hỏng bản dựng.
GIAO_DIEN = [
    ("3.2.1. Màn hình nhận diện trực tiếp",
     "Chức năng này hiển thị luồng video từ webcam và nhận diện liên tục mà không cần "
     "thao tác bấm chụp. Mỗi khuôn mặt phát hiện được vẽ khung bao, kèm tên, độ tin cậy "
     "và điểm chống giả mạo. Khung màu xanh nghĩa là đã xác nhận danh tính, màu vàng "
     "nghĩa là đang thu thập phiếu bầu, màu đỏ nghĩa là chưa nhận ra hoặc nghi ngờ giả "
     "mạo. Thanh bên phải hiển thị tốc độ khung hình và thời gian xử lý của từng tầng, "
     "phục vụ việc theo dõi hiệu năng.",
     "truc_tiep"),
    ("3.2.2. Màn hình kiosk điểm danh",
     "Đây là màn hình dành cho máy đặt ở cửa lớp. Giao diện được thiết kế tối giản với "
     "thẻ kết quả cỡ lớn đọc được từ xa: nền xanh khi điểm danh đúng giờ, nền vàng khi "
     "đi muộn hoặc bản ghi đang chờ đồng bộ, nền đỏ khi không nhận ra. Phía dưới là nhật "
     "ký lượt điểm danh trong buổi, số bản ghi đang chờ gửi lên máy chủ và nút đồng bộ "
     "thủ công.",
     "kiosk"),
    ("3.2.3. Màn hình đăng ký người dùng",
     "Chức năng đăng ký cho phép tạo hồ sơ mới rồi thu thập ảnh khuôn mặt theo hai cách: "
     "chụp trực tiếp nhiều lần từ webcam hoặc chọn tệp có sẵn. Ảnh được tổ chức theo thư "
     "mục mang tên người để tiện quản lý. Mỗi ảnh đưa vào đều đi qua cổng chất lượng và "
     "hiển thị kết quả ngay: ảnh không đạt sẽ kèm lý do cụ thể như \"ảnh mờ\" hoặc \"quay "
     "ngang quá nhiều\", giúp người dùng biết cần chụp lại thế nào.",
     "dang_ky"),
    ("3.2.4. Màn hình nhận diện ảnh tĩnh",
     "Chức năng này nhận một ảnh tải lên và trả về kết quả cho từng khuôn mặt tìm thấy, "
     "kèm điểm chất lượng, điểm tương đồng và điểm chống giả mạo. Nó phục vụ việc kiểm "
     "tra nhanh và việc đối chiếu khi có khiếu nại về bản ghi điểm danh.",
     "anh_tinh"),
    ("3.2.5. Màn hình kiểm tra chống giả mạo",
     "Chức năng dành riêng cho việc đánh giá tầng chống giả mạo. Người dùng đưa lần lượt "
     "mặt thật, ảnh in trên giấy và ảnh hiển thị trên màn hình điện thoại vào khung hình; "
     "hệ thống ghi lại điểm số của từng loại rồi tính các chỉ số APCER, BPCER và ACER "
     "theo tiêu chuẩn ISO/IEC 30107-3.",
     "chong_gia_mao"),
    ("3.2.6. Bảng điều khiển và đổi mô hình",
     "Bảng điều khiển hiển thị trạng thái hệ thống, số người đã đăng ký, số vector trong "
     "chỉ mục và mô hình đang sử dụng. Từ đây có thể đổi sang mô hình khác và dựng lại "
     "chỉ mục mà không cần khởi động lại chương trình — hữu ích khi cần cân đối giữa độ "
     "chính xác và tốc độ tuỳ theo cấu hình máy.",
     "bang_dieu_khien"),
    ("3.2.7. Màn hình nhận diện cử chỉ tay",
     "Chức năng này dùng chung tầng phát hiện của hệ thống nhưng đổi đối tượng từ khuôn "
     "mặt sang bàn tay. Hai mươi mốt điểm mốc trên bàn tay được suy ra từ mỗi khung "
     "hình, rồi phân loại thành ba cử chỉ: xoè bàn tay, chụm ngón và nắm tay. Mỗi cử chỉ "
     "kích hoạt một hiệu ứng hình ảnh vẽ chồng lên khung hình tại toạ độ ngón tay. Hiệu "
     "ứng được nhóm tự sinh bằng chương trình thay vì tải trên mạng, vì ba lý do: tránh "
     "ràng buộc bản quyền khi nộp bài, giữ đúng bảng màu của giao diện, và cho phép đổi "
     "màu hay kích thước bằng cách sửa tham số rồi chạy lại. Mỗi hiệu ứng là một thư mục "
     "ảnh PNG có nền trong suốt, nên thêm hiệu ứng mới chỉ là thả thư mục vào đúng chỗ, "
     "không phải sửa mã. Hiệu ứng chỉ phát khi cử chỉ **đổi** so với khung trước, tránh "
     "việc giữ nguyên một cử chỉ lại sinh ra hàng trăm hiệu ứng chồng nhau.",
     "cu_chi"),
    ("3.2.8. Giao diện web — trang tổng quan",
     "Trang tổng quan của giao diện web hiển thị các số liệu chính trong ngày: số người "
     "đã điểm danh, số đi muộn, tỉ lệ chuyên cần và biểu đồ xu hướng bảy ngày gần nhất. "
     "Đây là màn hình giảng viên mở đầu tiên.",
     "web_tong_quan"),
    ("3.2.9. Giao diện web — quản lý người",
     "Trang này liệt kê những người hệ thống có thể nhận diện, kèm số vector đặc trưng và "
     "số ảnh đã đăng ký của từng người — hai con số cho biết ngay hồ sơ nào còn mỏng dữ "
     "liệu. Từ đây có thể tìm theo tên hoặc mã, thêm người mới, đăng ký thêm ảnh và xoá "
     "hồ sơ.",
     "web_quan_ly"),
    ("3.2.10. Giao diện web — sổ điểm danh",
     "Sổ điểm danh hiển thị bản ghi theo khoảng ngày và theo buổi học, lọc theo trạng "
     "thái đúng giờ hoặc đi muộn, kèm số phút muộn, độ tin cậy nhận diện và mã thiết bị "
     "đã ghi nhận. Dữ liệu xuất được ra hai định dạng: CSV cho ai cần đưa sang công cụ "
     "khác, và tệp Excel đã định dạng sẵn để nộp hoặc lưu trữ. Chấm tròn \"Đang nhận trực "
     "tiếp\" ở góc trên cho biết kết nối thời gian thực đang mở, nên bản ghi mới hiện ra "
     "không cần tải lại trang.",
     "web_so_diem_danh"),
]

KET_LUAN = [
    ("p", "**Về những gì đề tài đã làm được.** Đối chiếu với mục tiêu đặt ra ở mục 1.2, "
          "hệ thống đã hoàn thành các nội dung sau."),
    ("p", "Về hệ thống ứng dụng, sản phẩm nhận diện được nhiều khuôn mặt trong luồng "
          "video thời gian thực, từ chối người chưa đăng ký thay vì gán bừa, ghi bản ghi "
          "điểm danh vào cơ sở dữ "
          "liệu với cơ chế chống ghi trùng ba tầng, hoạt động được khi mất kết nối nhờ "
          "hàng đợi trên đĩa, và có đủ cả ứng dụng máy tính lẫn giao diện web quản trị. "
          "Toàn bộ được đóng gói bằng Docker, khởi động bằng một lệnh."),
    ("p", "Về công nghệ, nhóm đã tự huấn luyện mạng trích đặc trưng bằng hàm mất mát "
          "ArcFace thay vì dùng lại mô hình có sẵn làm lõi. Mô hình tốt nhất do nhóm "
          "huấn luyện, thu được qua chưng cất tri thức trên 112 nghìn ảnh, đạt tỉ lệ "
          "đúng hạng nhất **0,9778** so với **0,9842** của mô hình thầy, trong khi "
          "**nhẹ hơn 22 lần** và **nhanh hơn 17,7 lần**. Cần nói rõ để tránh hiểu nhầm: "
          "cấu hình mặc định của sản phẩm vẫn đang chạy mô hình thầy FaceNet vì nó chính "
          "xác hơn và máy thử nghiệm có card đồ hoạ; mô hình do nhóm huấn luyện là lựa "
          "chọn cho máy yếu, đổi được ngay trong Bảng điều khiển. Hệ thống được đánh giá "
          "theo ba giao thức chuẩn với dữ liệu "
          "chia theo danh tính, và mỗi thành phần trong chuỗi xử lý đều được chứng minh "
          "đóng góp bằng thí nghiệm cắt bỏ."),
    ("p", "**Về những gì chưa làm được.** Báo cáo nêu rõ các hạn chế còn tồn tại thay vì "
          "chỉ trình bày kết quả thuận lợi."),
    ("li", "**Khoảng cách với mô hình thầy ở chỉ số open-set vẫn còn**: 0,7199 so với "
           "0,8513. Mô hình do nhóm huấn luyện xếp hạng gần bằng mô hình thầy nhưng điểm "
           "số của nó chưa được hiệu chỉnh tốt bằng, khiến việc phân định người quen và "
           "người lạ ở vùng ranh giới còn khó."),
    ("li", "**Phương pháp chống giả mạo bằng phân tích kết cấu ảnh đã thất bại hoàn "
           "toàn** và bị loại bỏ khỏi cấu hình mặc định. Nó được thay bằng phát hiện chớp "
           "mắt, đạt ACER 0 % trên cùng phép đo. Tuy nhiên kết quả đó mới chỉ trên **một "
           "phiên đo, một người, một thiết bị tấn công**, nên chưa đủ để tuyên bố hệ thống "
           "an toàn trước giả mạo. Hai điểm yếu đã biết của phương pháp chớp mắt vẫn chưa "
           "được kiểm chứng: video quay sẵn có người chớp mắt, và người đeo kính dày."),
    ("li", "**Tầng chống giả mạo chỉ được thực thi ở máy kiosk, không ở máy chủ**, vì nó "
           "cần chuỗi khung hình mà máy chủ không có. Một máy kiosk bị chiếm quyền có thể "
           "bỏ qua bước này — danh tính thì không giả mạo được, nhưng liveness thì có."),
    ("li", "**Cổng chất lượng chưa chứng minh được đóng góp đo đếm được.** Sau khi hiệu "
           "chỉnh ngưỡng theo dữ liệu webcam thật, tỉ lệ loại giảm từ 29,5 % xuống 1,9 % "
           "và không còn ai bị chặn khỏi đăng ký — nhưng đóng góp của cổng vào cả hai chỉ "
           "số nhận diện cũng về đúng bằng không. Nó được giữ lại vì chặn được phần đuôi "
           "thật sự hỏng và vì cung cấp phản hồi hướng dẫn cho người dùng, chứ không phải "
           "vì cải thiện được con số. Cần một tập kiểm tra thu từ webcam thật, thay cho "
           "ảnh báo chí, để đánh giá lại cho đúng."),
    ("li", "**Hệ thống chưa hỗ trợ buổi học kéo dài qua nửa đêm**, do ràng buộc giờ kết "
           "thúc phải lớn hơn giờ bắt đầu. Không ảnh hưởng tới điểm danh lớp học nhưng sẽ "
           "cần xử lý nếu mở rộng sang chấm công theo ca."),
    ("li", "**Chưa đánh giá trên dữ liệu người Việt.** Cả hai bộ dữ liệu huấn luyện đều "
           "thiên lệch về người phương Tây, nên kết quả thực tế trên sinh viên Việt Nam "
           "có thể khác con số báo cáo."),
    ("li", "**Mỗi lần điểm danh chỉ ghi được một người** — người đứng gần camera nhất. "
           "Đây là lựa chọn có chủ đích để tránh điểm danh nhầm người đi ngang qua phía "
           "sau, nhưng nó khiến kịch bản cả nhóm cùng đứng trước camera không dùng được."),
    ("li", "**Tầng chống giả mạo chưa chống được video quay sẵn.** Phương pháp chớp mắt "
           "chặn tốt ảnh tĩnh, nhưng một đoạn video có người chớp mắt thì về nguyên lý "
           "vẫn qua được. Chặn tới mức đó cần thử thách ngẫu nhiên — yêu cầu quay đầu "
           "theo hướng mà kẻ tấn công không đoán trước — và điều này chưa được cài đặt."),
    ("li", "**Ngưỡng 0,68 đánh đổi bằng việc từ chối oan 10,9 % lượt của người quen.** "
           "Cách khắc phục đúng không phải hạ ngưỡng mà là tăng số ảnh đăng ký cho mỗi "
           "người ở nhiều góc và điều kiện chiếu sáng khác nhau."),
    ("p", "**Về hướng phát triển.** Trên cơ sở những hạn chế trên, nhóm đề xuất các hướng "
          "tiếp theo, sắp xếp theo thứ tự ưu tiên."),
    ("p", "Trước tiên là những việc cần thiết để hoàn thiện các chức năng đã có. Thu thập "
          "dữ liệu khuôn mặt người Việt và huấn luyện lại để loại bỏ thiên lệch của bộ dữ "
          "liệu; đo lại tầng chống giả mạo trên tấn công vật lý thật và huấn luyện lại "
          "với dữ liệu đó; hiệu chỉnh ngưỡng cổng chất lượng theo ảnh webcam thực tế thay "
          "vì theo ảnh báo chí."),
    ("p", "Tiếp theo là các hướng mở rộng năng lực hệ thống. Về mặt mô hình, bổ sung ràng "
          "buộc về phân bố khoảng cách trong quá trình chưng cất để thu hẹp khoảng cách "
          "open-set với mô hình thầy. Về mặt chống giả mạo, hướng tiếp theo là **thử "
          "thách ngẫu nhiên** — yêu cầu quay đầu sang trái hoặc sang phải theo thứ tự "
          "không đoán trước được — vì phát hiện chớp mắt tuy chặn được ảnh in và ảnh "
          "trên màn hình nhưng **không chặn được video quay sẵn có người chớp mắt**; kẻ "
          "tấn công không đoán trước được yêu cầu nào sẽ xuất hiện thì video phát lại "
          "cũng vô dụng. Về mặt quy mô, thay chỉ mục tìm kiếm tuần tự bằng cấu trúc "
          "đồ thị phân cấp khi số người vượt vài nghìn."),
    ("p", "Về mặt quy trình phát triển, bài học lớn nhất của đề tài là cần đưa **người "
          "dùng thật** vào vòng kiểm thử sớm hơn. Tám lỗi nghiêm trọng nhất chỉ lộ ra khi "
          "có người thật sử dụng, trong khi 73 phép thử tự động đều xanh suốt thời gian "
          "chúng tồn tại — 73 là số phép thử có vào thời điểm đó, hai bộ cuối ở Bảng 3.19 "
          "được viết ra chính vì các lỗi này. Hướng cải thiện cụ thể: bổ sung kiểm thử cho **chỗ nối giữa "
          "các tầng chạy ở nhịp thời gian khác nhau**, kiểm thử cho **thao tác chuyển "
          "tiếp** giữa hai trạng thái chứ không chỉ đo từng trạng thái tĩnh, và dựng dữ "
          "liệu kiểm thử có **hình dạng đa dạng** thay vì chỉ lặp lại trường hợp đều "
          "nhất."),
    ("p", "Cuối cùng là các hướng mở rộng phạm vi ứng dụng: hỗ trợ ca làm việc qua đêm để "
          "dùng được cho chấm công doanh nghiệp; xây dựng ứng dụng di động cho phép giảng "
          "viên xem báo cáo và điểm danh bổ sung; và tích hợp với hệ thống quản lý đào "
          "tạo sẵn có của nhà trường để bản ghi điểm danh chảy thẳng vào sổ điểm."),
]


# ---------------------------------------------------------------- PHỤ LỤC
#: Phụ lục chỉ chứa thứ không thuộc về thân bài: địa chỉ mã nguồn, cách chạy
#: lại, và bảng tra cứu tệp. Số liệu và lập luận đều nằm ở Chương 3.
PHU_LUC = [
    ("p", "Toàn bộ mã nguồn của đề tài được công bố tại:"),
    ("p", "**https://github.com/thanhvuaws-jpg/XULYANHVATHIGIACMAYTINH**"),
    ("p", "Kho mã chứa mã nguồn, cấu hình triển khai, bộ kiểm thử và bốn mô hình đã "
          "huấn luyện ở định dạng ONNX, nên tải về là chạy được ngay mà không phải huấn "
          "luyện lại. Ba nhóm tệp **không** được đưa lên kho công khai: khoá bí mật của "
          "máy chủ, vì công bố nó đồng nghĩa với việc người ngoài tự tạo được thẻ quản "
          "trị hợp lệ; dữ liệu sinh trắc học và thông tin cá nhân, gồm ảnh khuôn mặt "
          "thật đã đăng ký và các tài liệu có họ tên kèm mã số sinh viên; và các tệp "
          "nặng sinh lại được, gồm hai bộ dữ liệu huấn luyện gần 4 GB cùng các tệp "
          "trọng số PyTorch khoảng 98 MB mỗi tệp."),
]
