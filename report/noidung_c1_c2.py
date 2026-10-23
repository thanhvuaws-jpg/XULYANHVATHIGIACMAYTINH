"""Nội dung Chương 1 và Chương 2 của báo cáo.

Tách nội dung khỏi mã dựng tài liệu để sửa chữ không phải đụng vào logic Word.

Quy ước ký hiệu dùng chung cho mọi tệp nội dung:
    ("h2",   "1.1. …")      mục cấp 2 — 14pt đậm
    ("h3",   "3.1.1. …")    mục cấp 3 — 13pt đậm
    ("p",    "…")           đoạn thân bài — 13pt, căn đều, thụt 1 cm, giãn 1,5
    ("li",   "…")           gạch đầu dòng
    ("cap",  "Hình 2.1. …") chú thích hình/bảng — 13pt nghiêng, căn giữa
    ("img",  "đường/dẫn")   ảnh
    ("tbl",  [[…], […]])    bảng
    ("br",   None)          ngắt trang
Chữ đặt giữa cặp ** sẽ thành chữ đậm.
"""

MO_DAU = [
    ("p", "Điểm danh thủ công trong lớp học vừa tốn thời gian vừa không đáng tin. "
          "Gọi tên lần lượt một lớp năm mươi sinh viên mất gần mười phút mỗi buổi, "
          "cộng dồn cả học kỳ là nhiều giờ giảng bị cắt mất; còn ký tên vào danh sách "
          "thì không ngăn được việc điểm danh hộ. Cả hai cách đều tạo ra dữ liệu phải "
          "nhập lại bằng tay trước khi dùng được cho việc gì khác."),
    ("p", "Đề tài này xây dựng một hệ thống điểm danh bằng nhận diện khuôn mặt để giải "
          "quyết đồng thời hai vấn đề trên: người học chỉ cần đi qua trước camera, hệ "
          "thống tự nhận ra và ghi thẳng vào cơ sở dữ liệu. Điểm khác biệt so với một "
          "bài tập nhận diện khuôn mặt thông thường là hệ thống được xây dựng theo "
          "hướng một sản phẩm hoàn chỉnh: có mô hình do nhóm tự huấn luyện chứ không "
          "chỉ gọi mô hình có sẵn, có tầng chống giả mạo để chặn việc giơ ảnh thay mặt "
          "thật, có máy chủ và cơ sở dữ liệu riêng, có cả ứng dụng máy tính lẫn giao "
          "diện web quản trị, và được đóng gói bằng Docker để triển khai bằng một lệnh."),
    ("p", "Toàn bộ quyết định kỹ thuật trong báo cáo đều được kiểm chứng bằng số đo "
          "trên cùng một tập kiểm tra. Khi một thay đổi không cải thiện kết quả, hoặc "
          "cải thiện mặt này nhưng làm xấu mặt kia, báo cáo nêu rõ điều đó thay vì chỉ "
          "kể những con số đẹp."),
]

CHUONG_1 = [
    ("h2", "1.1. Lý do chọn đề tài"),
    ("p", "Điểm danh là công việc lặp đi lặp lại ở mọi lớp học, và là công việc mà máy "
          "làm tốt hơn người. Ba lý do khiến nhóm chọn đề tài này:"),
    ("li", "**Tính cấp thiết.** Cách điểm danh hiện tại tiêu tốn thời gian giảng dạy và "
           "không chống được gian lận. Một hệ thống tự động vừa trả lại thời gian cho "
           "lớp học, vừa gắn mỗi bản ghi với một khuôn mặt cụ thể."),
    ("li", "**Tính ứng dụng.** Sản phẩm không dừng ở mức minh hoạ thuật toán. Nó có thể "
           "đặt ngay ở cửa lớp và dùng được: một máy tính có camera chạy ứng dụng kiosk, "
           "một máy chủ chạy API và cơ sở dữ liệu, giảng viên xem báo cáo qua trình duyệt."),
    ("li", "**Tính học thuật.** Nhận diện khuôn mặt là bài toán **open-set**: hệ thống "
           "phải nhận ra người đã đăng ký và đồng thời **từ chối người chưa đăng ký**. "
           "Đây là điểm khiến bài toán khó hơn phân loại thông thường, và cũng là nơi "
           "phần lớn các báo cáo đánh giá sai. Đề tài đi qua trọn vẹn quy trình: chuẩn "
           "bị dữ liệu, huấn luyện mạng tích chập, đánh giá theo giao thức chuẩn, tối ưu "
           "và triển khai."),
    ("p", "Ngoài ra, hệ thống nhận diện khuôn mặt không có tầng chống giả mạo thì mọi "
          "độ chính xác đạt được đều vô nghĩa về mặt an ninh: chỉ cần giơ ảnh chân dung "
          "trong điện thoại trước camera là điểm danh hộ được. Đề tài vì vậy đưa cả bài "
          "toán phát hiện tấn công trình diện vào phạm vi thực hiện."),

    ("h2", "1.2. Mục tiêu đề tài"),
    ("p", "**Hệ thống làm gì và làm cho ai.** Hệ thống ghi nhận sự có mặt của sinh viên "
          "trong một buổi học bằng cách nhận diện khuôn mặt qua camera, không cần thao "
          "tác thủ công. Ba nhóm người dùng: sinh viên đứng trước camera kiosk; giảng "
          "viên xem và xuất báo cáo điểm danh; quản trị viên đăng ký người mới, tạo buổi "
          "học và cấu hình hệ thống."),
    ("p", "**Kết quả cần đạt được về hệ thống ứng dụng:**"),
    ("li", "Nhận diện thời gian thực từ webcam ở tốc độ tối thiểu 25 khung hình mỗi giây "
           "trên máy tính phổ thông, nhận diện được nhiều người trong cùng một khung hình."),
    ("li", "Từ chối người chưa đăng ký thay vì gán bừa cho người giống nhất."),
    ("li", "Chặn được tấn công bằng ảnh in và ảnh hiển thị trên màn hình. "
           "*(Mục tiêu này chưa đạt — xem phân tích ở mục 3.1.9 và phần Kết luận.)*"),
    ("li", "Ghi bản ghi điểm danh vào cơ sở dữ liệu, phân biệt đúng giờ và đi muộn, "
           "chống ghi trùng, xuất được báo cáo."),
    ("li", "Hoạt động được cả khi mất kết nối mạng: bản ghi xếp hàng trên đĩa và tự đồng "
           "bộ khi mạng trở lại."),
    ("li", "Có ứng dụng máy tính cho kiosk và giao diện web cho quản trị; triển khai được "
           "bằng một lệnh Docker."),
    ("p", "**Kết quả cần đạt được về công nghệ ứng dụng:**"),
    ("li", "Tự huấn luyện mạng tích chập trích đặc trưng khuôn mặt bằng hàm mất mát "
           "ArcFace, không dùng lại mô hình có sẵn làm lõi sản phẩm."),
    ("li", "Đánh giá theo ba giao thức chuẩn — xác thực 1:1, định danh đóng 1:N và định "
           "danh mở — thay cho một con số độ chính xác đơn lẻ."),
    ("li", "Thu nhỏ mô hình bằng chưng cất tri thức để chạy được trên máy yếu, đồng thời "
           "đo rõ phần độ chính xác phải đánh đổi."),

    ("h2", "1.3. Phạm vi đề tài"),
    ("p", "**Phạm vi về bài toán.** Đề tài giải quyết nhận diện 1:N trong một tập người "
          "đã đăng ký có quy mô lớp học hoặc phòng ban, cỡ vài chục tới vài nghìn người. "
          "Không đặt mục tiêu nhận diện đám đông quy mô thành phố, không xử lý khuôn mặt "
          "bị che quá một nửa, và không nhận diện qua video giám sát ở khoảng cách xa."),
    ("p", "**Phạm vi về dữ liệu.** Huấn luyện trên hai bộ dữ liệu công khai là LFW và "
          "CASIA-WebFace. Dữ liệu người dùng thật do chính hệ thống thu thập ở khâu đăng "
          "ký và chỉ dùng để tra cứu, không dùng để huấn luyện lại."),
    ("p", "**Phạm vi về chống giả mạo.** Tầng chống giả mạo nhắm vào hai kiểu tấn công "
          "phổ biến nhất và rẻ nhất: ảnh in trên giấy và ảnh hiển thị trên màn hình điện "
          "thoại. Không xử lý mặt nạ silicon ba chiều hay video giả mạo bằng học sâu."),
    ("p", "**Phạm vi về thời gian và thiết bị.** Thực hiện trong khoảng tám tuần trên một "
          "máy tính chạy Windows 11, card đồ hoạ NVIDIA GTX 1650 4 GB. Giới hạn phần "
          "cứng này ảnh hưởng trực tiếp tới lựa chọn kiến trúc mạng và được nêu rõ ở "
          "Chương 3."),

    ("h2", "1.4. Đối tượng nghiên cứu"),
    ("li", "**Ảnh và luồng video khuôn mặt người** thu từ webcam và từ các bộ dữ liệu "
           "công khai, trong điều kiện chiếu sáng và góc chụp không kiểm soát."),
    ("li", "**Các mô hình mạng tích chập trích đặc trưng khuôn mặt**: MobileFaceNet, "
           "InceptionResnetV1, cùng hàm mất mát ArcFace và kỹ thuật chưng cất tri thức."),
    ("li", "**Các mô hình phát hiện khuôn mặt**: MTCNN và YuNet."),
    ("li", "**Giao thức đánh giá hệ thống sinh trắc học**: TAR@FAR, đường cong CMC, "
           "DIR@FAR, và bộ chỉ số APCER/BPCER/ACER theo ISO/IEC 30107-3 dành cho phát "
           "hiện tấn công trình diện."),
    ("li", "**Kiến trúc phần mềm client–server** cho một hệ thống sinh trắc học có ràng "
           "buộc thời gian thực."),

    ("h2", "1.5. Phương pháp nghiên cứu"),
    ("p", "**Phương pháp thu thập thông tin.** Nghiên cứu các bài báo gốc của những kỹ "
          "thuật được sử dụng (liệt kê ở Danh mục tài liệu tham khảo), đọc tài liệu và "
          "mã nguồn của các thư viện OpenCV, PyTorch và ONNX Runtime. Dữ liệu huấn luyện "
          "lấy từ hai bộ công khai đã được cộng đồng dùng làm chuẩn so sánh."),
    ("p", "**Phương pháp thực nghiệm có đối chứng.** Đây là phương pháp chủ đạo của đề "
          "tài. Mỗi thay đổi kỹ thuật đều được đo trước và sau trên **cùng một tập kiểm "
          "tra, cùng một chỉ số**, và chỉ được giữ lại nếu số đo chứng minh nó có ích. "
          "Với các thành phần đã đưa vào hệ thống, nhóm thực hiện thêm thí nghiệm cắt bỏ "
          "(ablation): tắt từng thành phần rồi đo lại, chênh lệch chính là đóng góp thật "
          "của thành phần đó. Kết quả trình bày ở mục 3.1.10."),
    ("p", "**Phương pháp đánh giá đúng chuẩn.** Tập dữ liệu được chia theo **danh tính** "
          "chứ không theo ảnh, bảo đảm người xuất hiện trong tập kiểm tra chưa từng xuất "
          "hiện lúc huấn luyện. Kết quả báo cáo theo ba giao thức chuẩn thay vì một con "
          "số độ chính xác duy nhất. Lý do của lựa chọn này được phân tích ở mục 2.3."),
    ("p", "**Phương pháp phát triển phần mềm.** Xây dựng theo từng bước, mỗi bước có bộ "
          "kiểm thử tự động chạy được lại bất cứ lúc nào. Hệ thống hoàn chỉnh có bảy bộ "
          "kiểm thử với tổng cộng 85 phép thử, trong đó hai bộ gọi qua giao thức HTTP "
          "vào hệ thống đã triển khai thật chứ không gọi vào mã nguồn."),
    ("p", "Phần còn lại của báo cáo được tổ chức như sau."),
    ("p", "**Chương 2** trình bày cơ sở lý thuyết của ba nhóm kỹ thuật được sử dụng. "
          "Mục 2.1 phân tích bài toán phát hiện khuôn mặt và so sánh hai hướng tiếp cận "
          "là mạng nối tiếp nhiều giai đoạn MTCNN và mạng một giai đoạn YuNet. Mục 2.2 "
          "trình bày cách một mạng tích chập biến khuôn mặt thành vector đặc trưng, vì "
          "sao hàm mất mát ArcFace cho vector phân tách tốt hơn hàm mất mát phân loại "
          "thông thường, và vai trò của bước căn chỉnh khuôn mặt. Mục 2.3 trình bày kỹ "
          "thuật chưng cất tri thức dùng để thu nhỏ mô hình, cùng giao thức đánh giá "
          "open-set và lý do vì sao cách đánh giá thông thường cho kết quả sai lệch."),
    ("p", "**Chương 3** trình bày quá trình phân tích, xây dựng và kiểm chứng sản phẩm. "
          "Mục 3.1 mô tả kiến trúc hệ thống, thiết kế cơ sở dữ liệu, quá trình huấn "
          "luyện mô hình cùng toàn bộ số liệu đo được, tầng chống giả mạo, thí nghiệm "
          "cắt bỏ và việc đóng gói triển khai. Mục 3.2 giới thiệu giao diện của từng "
          "chức năng trong ứng dụng máy tính và trên giao diện web quản trị."),
    ("p", "**Kết luận** đối chiếu kết quả đạt được với mục tiêu đề ra ở mục 1.2, nêu rõ "
          "những hạn chế còn tồn tại và hướng phát triển tiếp theo."),
]

CHUONG_2 = [
    ("p", "Hệ thống nhận diện khuôn mặt không phải một mô hình duy nhất mà là một chuỗi "
          "xử lý gồm nhiều tầng, mỗi tầng giải một bài toán con khác nhau. Chương này "
          "trình bày cơ sở lý thuyết của ba nhóm kỹ thuật quyết định chất lượng hệ thống: "
          "phát hiện khuôn mặt (mục 2.1), trích đặc trưng và hàm mất mát ArcFace "
          "(mục 2.2), chưng cất tri thức cùng giao thức đánh giá open-set (mục 2.3)."),
    ("p", "Ba nhóm này được chọn vì chúng tương ứng với ba câu hỏi mà đề tài buộc phải "
          "trả lời: **tìm khuôn mặt ở đâu trong ảnh** và tìm đủ nhanh để chạy thời gian "
          "thực; **mô tả khuôn mặt bằng con số như thế nào** để hai ảnh của cùng một "
          "người cho hai vector gần nhau; và **làm sao biết hệ thống thực sự tốt tới "
          "đâu** khi nó phải hoạt động với cả những người nó chưa từng nhìn thấy."),

    ("h2", "2.1. Phát hiện khuôn mặt: MTCNN và YuNet"),
    ("p", "Phát hiện khuôn mặt là tầng đầu tiên và là tầng quyết định giới hạn tốc độ "
          "của cả hệ thống, vì nó phải chạy trên **toàn bộ** khung hình ở mọi khung, "
          "trong khi các tầng sau chỉ chạy trên phần ảnh đã cắt ra. Đầu ra của tầng này "
          "gồm hộp bao quanh mỗi khuôn mặt và năm điểm mốc: hai mắt, mũi và hai khoé "
          "miệng — năm điểm này là đầu vào bắt buộc cho bước căn chỉnh ở mục 2.2."),
    ("h3", "2.1.1. MTCNN — mạng nối tiếp ba giai đoạn"),
    ("p", "MTCNN (Multi-task Cascaded Convolutional Networks) giải bài toán bằng ba mạng "
          "tích chập nhỏ nối tiếp nhau, mỗi mạng lọc bớt ứng viên cho mạng sau:"),
    ("li", "**P-Net** quét toàn ảnh ở nhiều tỉ lệ trong một kim tự tháp ảnh, sinh ra rất "
           "nhiều ứng viên thô."),
    ("li", "**R-Net** nhận các ứng viên đó, loại phần lớn ứng viên sai và tinh chỉnh hộp bao."),
    ("li", "**O-Net** đưa ra hộp bao cuối cùng cùng năm điểm mốc."),
    ("p", "Thiết kế nối tiếp cho độ chính xác cao vì mỗi giai đoạn được huấn luyện riêng "
          "cho đúng phần việc của nó. Nhược điểm nằm ở chỗ chi phí tính toán **tăng theo "
          "số khuôn mặt trong ảnh**: ảnh càng đông người thì càng nhiều ứng viên phải đi "
          "qua R-Net và O-Net. Đây chính là điểm khiến MTCNN không phù hợp với kịch bản "
          "lớp học, như số liệu đo ở mục 3.1.3 cho thấy."),
    ("h3", "2.1.2. YuNet — mạng một giai đoạn"),
    ("p", "YuNet đi theo hướng ngược lại: một mạng tích chập duy nhất, chạy một lần trên "
          "ảnh đã thu nhỏ về kích thước cố định, dự đoán đồng thời hộp bao, điểm tin cậy "
          "và năm điểm mốc. Mạng chỉ có khoảng 75 nghìn tham số và tệp mô hình nặng "
          "232 KB, được phân phối sẵn ở định dạng ONNX và tích hợp thẳng trong OpenCV "
          "qua lớp cv2.FaceDetectorYN."),
    ("p", "Vì mạng chạy đúng một lần bất kể ảnh có bao nhiêu khuôn mặt, chi phí tính "
          "toán **gần như không đổi theo số người trong khung hình**. Đây là tính chất "
          "quyết định đối với một hệ thống điểm danh, nơi nhiều người có thể cùng xuất "
          "hiện trước camera."),
    ("p", "Một chi tiết quan trọng về mặt kỹ thuật: năm điểm mốc mà YuNet trả về có "
          "**cùng thứ tự** với mẫu chuẩn của ArcFace, nên dùng được ngay cho bước căn "
          "chỉnh mà không phải sắp xếp lại."),

    ("h2", "2.2. Trích đặc trưng khuôn mặt và hàm mất mát ArcFace"),
    ("h3", "2.2.1. Căn chỉnh khuôn mặt bằng phép biến đổi tương tự"),
    ("p", "Trước khi đưa vào mạng trích đặc trưng, khuôn mặt phải được đưa về một tư thế "
          "chuẩn. Nếu bỏ qua bước này, cùng một người chụp nghiêng đầu hai kiểu khác "
          "nhau sẽ cho hai vector cách xa nhau, và mạng buộc phải học thêm tính bất biến "
          "với phép xoay — việc mà một phép biến đổi hình học giải được chính xác và "
          "gần như miễn phí."),
    ("p", "Cách làm: định nghĩa một **mẫu chuẩn** gồm toạ độ mong muốn của năm điểm mốc "
          "trên ảnh 112×112 pixel, rồi tìm phép biến đổi tương tự (gồm xoay, tịnh tiến "
          "và co giãn đồng đều) đưa năm điểm mốc thực tế về gần mẫu chuẩn nhất. Phép "
          "biến đổi này được ước lượng bằng hàm cv2.estimateAffinePartial2D."),
    ("p", "Điểm cần lưu ý là phép biến đổi tương tự có bốn bậc tự do trong khi ta có mười "
          "ràng buộc (năm điểm, mỗi điểm hai toạ độ), nên bài toán thừa xác định và phải "
          "giải theo nghĩa xấp xỉ. Đề tài dùng ước lượng bền vững theo tiêu chuẩn trung "
          "vị bình phương nhỏ nhất thay vì bình phương tối thiểu thông thường, để một "
          "điểm mốc bị lệch — chuyện thường xảy ra khi mặt quay ngang và một mắt bị che "
          "— không kéo lệch cả phép biến đổi."),
    ("p", "Một hệ quả đáng chú ý được dùng ở mục 3.1.4: vì phép biến đổi đã xoay thẳng "
          "khuôn mặt, **góc nghiêng đầu trong mặt phẳng ảnh gần như không gây hại**, "
          "trong khi **góc quay ngang** lại làm mất hẳn thông tin của một bên mặt và "
          "không phép biến đổi hai chiều nào cứu được."),
    ("h3", "2.2.2. Vector đặc trưng và độ đo cosine"),
    ("p", "Mạng trích đặc trưng biến ảnh khuôn mặt 112×112 thành một vector 512 chiều. "
          "Vector này được **chuẩn hoá về độ dài bằng 1**, nhờ đó tích vô hướng của hai "
          "vector chính bằng cosin của góc giữa chúng, nhận giá trị trong đoạn từ −1 tới "
          "1. Hai ảnh của cùng một người cho giá trị gần 1, hai người khác nhau cho giá "
          "trị gần 0."),
    ("p", "Việc chuẩn hoá không chỉ để tiện tính toán. Nó ép toàn bộ không gian đặc trưng "
          "nằm trên mặt cầu đơn vị, biến bài toán so khớp thành bài toán đo góc — và "
          "chính trên mặt cầu này hàm mất mát ArcFace mới phát huy tác dụng."),
    ("h3", "2.2.3. Hàm mất mát ArcFace"),
    ("p", "Nếu huấn luyện mạng bằng hàm mất mát phân loại thông thường, mạng chỉ cần học "
          "sao cho mỗi người rơi đúng vào lớp của mình. Điều đó **không** bảo đảm rằng "
          "hai người khác nhau nằm cách xa nhau: các lớp chỉ cần tách được là đủ, dù "
          "ranh giới giữa chúng sát tới đâu. Hậu quả là mô hình phân loại rất tốt những "
          "người đã học nhưng cho vector kém phân tách với người chưa từng thấy — trong "
          "khi đó mới đúng là việc hệ thống phải làm."),
    ("p", "ArcFace sửa điều này bằng cách cộng thêm một **biên độ góc** vào góc giữa "
          "vector đặc trưng và vector trọng số của lớp đúng, trước khi tính hàm mất mát. "
          "Mạng vì thế bị buộc phải đẩy mẫu của lớp đúng lại gần tâm lớp thêm một khoảng "
          "góc nữa so với mức tối thiểu cần để phân loại đúng. Kết quả là các lớp tách "
          "nhau với một khoảng đệm rõ ràng trên mặt cầu, và khoảng đệm đó vẫn còn giá "
          "trị với những danh tính mạng chưa từng gặp."),
    ("p", "Biên độ càng lớn thì bài toán càng bị siết chặt. Số đo cụ thể của hiệu ứng "
          "này, cùng lý do vì sao phải tăng biên độ **dần dần** thay vì đặt giá trị cuối "
          "ngay từ đầu, được trình bày ở mục 3.1.5."),
    ("h3", "2.2.4. MobileFaceNet — kiến trúc mạng được chọn"),
    ("p", "Đề tài chọn MobileFaceNet làm kiến trúc trích đặc trưng thay vì các mạng sâu "
          "như ResNet50. Ba lý do:"),
    ("li", "**Số tham số nhỏ**: khoảng 1,2 triệu, so với 25 triệu của ResNet50. Với chỉ "
           "một card GTX 1650 4 GB và vài tuần thực hiện, một mạng lớn không thể huấn "
           "luyện tới hội tụ."),
    ("li", "**Tích chập tách theo chiều sâu** giúp giảm mạnh khối lượng tính toán mà giữ "
           "được khả năng biểu diễn, phù hợp với yêu cầu chạy thời gian thực."),
    ("li", "**Tích chập toàn cục theo chiều sâu ở tầng cuối** thay cho phép lấy trung "
           "bình toàn cục. Đây là chi tiết đặc trưng của kiến trúc này: lấy trung bình "
           "toàn cục coi mọi vị trí trên bản đồ đặc trưng là như nhau, trong khi ở khuôn "
           "mặt đã căn chỉnh, vùng trung tâm chứa mắt mũi rõ ràng quan trọng hơn vùng "
           "rìa. Tích chập toàn cục theo chiều sâu cho phép mạng tự học trọng số riêng "
           "cho từng vị trí."),

    ("h2", "2.3. Chưng cất tri thức và giao thức đánh giá open-set"),
    ("h3", "2.3.1. Chưng cất tri thức"),
    ("p", "Huấn luyện một mạng từ đầu trên lượng dữ liệu vừa phải cho kết quả hạn chế, "
          "trong khi các mô hình công khai đã được huấn luyện trên hàng triệu ảnh. Chưng "
          "cất tri thức là cách chuyển năng lực của một mô hình lớn (gọi là **thầy**) "
          "sang một mô hình nhỏ (gọi là **trò**)."),
    ("p", "Ở bài toán phân loại thông thường, trò học theo phân bố xác suất mềm mà thầy "
          "sinh ra. Với nhận diện khuôn mặt, đề tài áp dụng một biến thể phù hợp hơn: "
          "trò học **hồi quy trực tiếp vector đặc trưng** của thầy, với hàm mục tiêu là "
          "khoảng cách cosine giữa vector của trò và vector của thầy trên cùng một ảnh."),
    ("p", "Cách này có hai lợi thế quan trọng. Thứ nhất, đích học là một vector 512 "
          "chiều — mang nhiều thông tin hơn hẳn một nhãn một-trong-N, nên mỗi ảnh dạy "
          "được cho trò nhiều hơn. Thứ hai, và quan trọng hơn về mặt thực hành: **trò "
          "không cần nhãn danh tính**. Chỉ cần đưa ảnh qua thầy để lấy vector đích, nên "
          "mọi ảnh khuôn mặt đều dùng được, kể cả ảnh không có nhãn."),
    ("h3", "2.3.2. Vì sao phải chia dữ liệu theo danh tính"),
    ("p", "Một sai lầm phổ biến khi đánh giá hệ thống nhận diện khuôn mặt là chia tập "
          "kiểm tra theo **ảnh**: lấy một số ảnh của mỗi người làm tập đăng ký, số còn "
          "lại làm tập truy vấn. Cách chia này khiến mọi người trong tập kiểm tra đều đã "
          "xuất hiện lúc huấn luyện, và kết quả thu được đo bài toán *nhận lại người đã "
          "học* chứ không phải *nhận ra người chưa từng gặp*."),
    ("p", "Trong khi đó, hệ thống thực tế luôn phải làm việc với người mới: mỗi lần đăng "
          "ký một sinh viên là thêm một danh tính mà mô hình chưa hề được huấn luyện "
          "trên đó. Muốn con số báo cáo phản ánh đúng năng lực này, ranh giới giữa các "
          "tập phải đặt ở mức **danh tính**. Mức chênh lệch giữa hai cách chia được đo "
          "cụ thể ở mục 3.1.6."),
    ("h3", "2.3.3. Ba giao thức đánh giá"),
    ("p", "Một con số độ chính xác duy nhất không mô tả được hệ thống sinh trắc học, vì "
          "nó không cho biết hệ thống sai theo kiểu nào. Đề tài dùng ba giao thức, mỗi "
          "giao thức trả lời một câu hỏi khác nhau:"),
    ("li", "**Xác thực 1:1.** Cho hai ảnh, hỏi có phải cùng một người không. Kết quả cho "
           "ra đường cong ROC, diện tích dưới đường cong, tỉ lệ lỗi cân bằng, và quan "
           "trọng nhất là **TAR@FAR** — tỉ lệ chấp nhận đúng ở một mức chấp nhận sai cho "
           "trước. Chỉ số này cần thiết vì trong ứng dụng an ninh, hai loại lỗi không hề "
           "ngang giá nhau."),
    ("li", "**Định danh đóng 1:N.** Mọi người truy vấn đều đã đăng ký; hỏi hệ thống xếp "
           "đúng người ở hạng mấy. Kết quả cho ra tỉ lệ đúng ở hạng nhất, hạng năm và "
           "đường cong CMC."),
    ("li", "**Định danh mở.** Trong dòng người truy vấn có cả người **chưa** đăng ký. Hệ "
           "thống phải nhận ra người quen và đồng thời từ chối người lạ. Kết quả cho ra "
           "**DIR@FAR**: ở mức chấp nhận x phần trăm người lạ bị nhận nhầm thì nhận đúng "
           "được bao nhiêu phần trăm người quen."),
    ("p", "Giao thức thứ ba mới đúng là bài toán điểm danh, và cũng là giao thức khắc "
          "nghiệt nhất. Một hệ thống có thể đạt tỉ lệ đúng hạng nhất rất cao mà vẫn kém "
          "ở định danh mở, vì xếp hạng đúng là một chuyện, còn **dám khẳng định** hay "
          "không lại đòi hỏi điểm số phải đáng tin cậy ở mức tuyệt đối. Hiện tượng này "
          "quan sát được rõ trong kết quả ở mục 3.1.7."),
    ("h3", "2.3.4. Đánh giá tầng chống giả mạo"),
    ("p", "Tầng chống giả mạo được đánh giá theo bộ chỉ số của tiêu chuẩn ISO/IEC "
          "30107-3, gồm ba đại lượng: **APCER** là tỉ lệ tấn công lọt qua; **BPCER** là "
          "tỉ lệ người thật bị từ chối oan; và **ACER** là trung bình của hai đại lượng "
          "trên. Cần cả ba vì một mô hình từ chối mọi thứ sẽ có APCER bằng không nhưng "
          "hoàn toàn vô dụng — một cạm bẫy mà đề tài đã gặp phải trong thực tế, trình "
          "bày ở mục 3.1.9."),
]
