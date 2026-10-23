"""Mục 3.1.15 — kiểm thử với người dùng thật.

Tách ra tệp riêng vì đây là phần nội dung có giá trị học thuật cao nhất của
chương 3: tám lỗi, không lỗi nào bị các phép thử tự động phát hiện, và tất cả chỉ
lộ ra khi một người thật ngồi trước camera và thử phá.
"""

NGUOI_DUNG_THAT = [
    ("h3", "3.1.16. Kiểm thử với người dùng thật và tám lỗi chỉ lộ ra khi đó"),
    ("p", "Sau khi hệ thống vượt qua toàn bộ bộ kiểm thử tự động và đạt ACER 0 % trên "
          "phép đo chống giả mạo, nhóm đưa sản phẩm cho một người dùng thật ngồi trước "
          "camera và thử phá. Tám lỗi được phát hiện. **Không lỗi "
          "nào trong số đó bị các bộ kiểm thử tự động bắt được.**"),
    ("p", "Phần này trình bày cả tám, vì chúng cho thấy một điều quan trọng hơn bản thân "
          "từng lỗi: các phép đo trong phòng thí nghiệm kiểm tra **từng tầng riêng lẻ ở "
          "trạng thái tĩnh**, trong khi lỗi thật phần lớn nằm ở **chỗ nối giữa các tầng** "
          "và ở **thao tác chuyển tiếp** giữa hai trạng thái."),

    ("tbl", [["#", "Lỗi", "Biểu hiện với người dùng"],
             ["1", "Cổng chất lượng quá gắt", "Đăng ký 12 ảnh chỉ 4 ảnh được nhận"],
             ["2", "Chống giả mạo bằng kết cấu ảnh chấm ngược",
              "Ảnh điện thoại được coi là thật hơn người thật"],
             ["3", "Bằng chứng sống gắn vào toạ độ màn hình",
              "Giơ ảnh vào đúng chỗ mặt vừa rời đi là qua được"],
             ["4", "Công thức EAR không bất biến theo tỉ lệ",
              "Đứng xa bị báo giả mạo, lại gần thì hết"],
             ["5", "Nhập nhèm chưa-đo-được với là-giả",
              "Vừa bước vào khung hình đã bị kết tội giả mạo"],
             ["6", "Ngưỡng nhận diện quá thấp",
              "Video người khác được gán tên người đã đăng ký"],
             ["7", "Vết bị tiêu thụ khi còn đang chờ xác minh",
              "Khung xanh, điểm sống 1,00, mà không có bản ghi nào"],
             ["8", "Tỉ lệ chuyên cần chia sai đơn vị",
              "Bảng điều khiển hiện tỉ lệ chuyên cần 133 %"]]),
    ("cap", "Bảng 3.20. Tám lỗi phát hiện khi người dùng thật sử dụng hệ thống"),

    ("p", "**Lỗi 1 — cổng chất lượng quá gắt.** Ngưỡng độ nét 0,025 hiệu chỉnh theo ảnh "
          "báo chí của bộ LFW tỏ ra sai hoàn toàn với ảnh webcam. Chi tiết và cách đo lại "
          "đã trình bày ở mục 3.1.10."),

    ("p", "**Lỗi 2 — phương pháp chống giả mạo chấm ngược.** Đã trình bày ở mục 3.1.9. "
          "Điểm đáng nhớ: mô hình chấm ảnh điện thoại **thật hơn** khuôn mặt thật."),

    ("p", "**Lỗi 3 — bằng chứng sống gắn vào một toạ độ, không gắn vào một người.** Sau "
          "khi chuyển sang phát hiện chớp mắt, hệ thống ghép mỗi khuôn mặt vào một \"ô "
          "theo dõi\" dựa trên khoảng cách tâm hộp bao, và ô đó giữ lịch sử chớp mắt "
          "vĩnh viễn. Hậu quả: người dùng chớp mắt, hạ mặt xuống, rồi giơ ảnh điện thoại "
          "vào **đúng chỗ mặt vừa rời đi** — tấm ảnh ghép trúng ô cũ và **thừa hưởng cái "
          "chớp mắt** của người thật. Ảnh tĩnh được chấm 0,92 điểm sống."),
    ("p", "Điều đáng nói là chính nhóm đã ghi nhận rủi ro này trong tài liệu mã nguồn khi "
          "nới cửa sổ hiệu lực của một lần chớp từ 6 lên 15 giây, rồi đánh giá nó là "
          "\"khó hơn hẳn việc chỉ giơ một tấm ảnh lên\" và bỏ qua. Người dùng chứng minh "
          "đòn đó mất hai giây. Cách sửa: ô theo dõi không thấy mặt quá 0,6 giây thì bị "
          "xoá cùng toàn bộ lịch sử, buộc bằng chứng sống phải thuộc về một khuôn mặt "
          "được theo dõi **liên tục**."),

    ("p", "**Lỗi 4 — công thức EAR không bất biến theo tỉ lệ như lý thuyết gợi ý.** Tỉ lệ "
          "khung hình mắt (EAR) về mặt toán học là một tỉ số nên lẽ ra không phụ thuộc "
          "kích thước. Đo thực tế trên cùng một bộ ảnh, mắt **luôn mở**, chỉ thay đổi cỡ "
          "khuôn mặt, cho kết quả khác hẳn."),
    ("tbl", [["Cỡ khuôn mặt", "EAR đo được", "Ghi chú"],
             ["60 px", "0,2044", ""],
             ["80 px", "0,1124", "thấp hơn cả ngưỡng \"đang nhắm\" 0,16"],
             ["100 px", "0,1371", ""],
             ["130 px", "0,1531", ""],
             ["220 px", "0,2123", "vẫn chưa chạm ngưỡng \"đã mở\" 0,22"]]),
    ("cap", "Bảng 3.21. EAR của mắt đang mở thay đổi theo kích thước khuôn mặt"),
    ("p", "Nguyên nhân: sai số định vị điểm mốc lấn át tín hiệu thật khi mắt chỉ còn vài "
          "chục điểm ảnh. Hậu quả quan sát được: người đứng xa thì mắt bị coi là **nhắm "
          "vĩnh viễn**, máy trạng thái không bao giờ thấy chuỗi mở → nhắm → mở, không "
          "đếm được cái chớp nào, và người thật bị kết tội giả mạo; lại gần thì đột nhiên "
          "chạy được."),
    ("p", "Cách sửa là bỏ ngưỡng tuyệt đối lấy từ tài liệu, chuyển sang **ngưỡng tương "
          "đối theo từng người**: mỗi khuôn mặt tự dựng đường nền EAR lúc mắt mở, rồi coi "
          "là chớp khi EAR tụt dưới 72 % đường nền ấy và bật lại trên 85 %. Cách này bất "
          "biến với cả cỡ mặt lẫn hình dạng mắt từng người."),

    ("p", "**Lỗi 5 — nhập nhèm \"chưa đo được\" với \"đã đo và là giả\".** Khi khuôn mặt "
          "quá nhỏ hoặc vừa mới xuất hiện, hệ thống trả về điểm sống 0,0 — cùng giá trị "
          "với kết luận \"đây là giả mạo\". Người dùng vừa bước vào khung hình đã bị gắn "
          "nhãn giả mạo, trong khi hệ thống **chưa quan sát được gì**."),
    ("p", "Đây là dạng lỗi rất dễ mắc và khó thấy: dùng một giá trị hợp lệ để biểu thị "
          "trạng thái \"không có giá trị\". Nó không gây lỗi chương trình, chỉ lặng lẽ "
          "biến \"tôi không biết\" thành \"tôi khẳng định là giả\". Cách sửa: thêm giá "
          "trị riêng −1,0 nghĩa là chưa xác định, cùng một khoảng chờ hợp lý trước khi "
          "kết luận. Giao diện chuyển sang **ba trạng thái ba màu** thay vì hai."),
    ("tbl", [["Màu", "Nghĩa", "Có ghi điểm danh không"],
             ["Vàng", "Đang kiểm tra — chưa đủ bằng chứng", "Không"],
             ["Xanh", "Người thật, đã nhận ra", "Có"],
             ["Đỏ", "Đã xét đủ và kết luận là giả", "Không"]]),
    ("cap", "Bảng 3.22. Ba trạng thái hiển thị của tầng chống giả mạo"),
    ("p", "Trạng thái vàng là thứ bản đầu thiếu hoàn toàn. Hệ thống chỉ có hai màu nên "
          "buộc phải chọn một trong hai ngay lập tức, và nó chọn sai. Thêm vào đó, trạng "
          "thái vàng **không hiển thị tên người** — một kết quả chưa được xác nhận không "
          "được phép trình bày y như một kết luận."),

    ("p", "**Lỗi 6 — ngưỡng nhận diện quá thấp.** Người dùng giơ điện thoại phát video "
          "của một người hoàn toàn khác; hệ thống chấm 0,756 và gán đúng tên người đã "
          "đăng ký. Đo lại trên 632 ảnh người quen và 474 ảnh người lạ cho thấy mức độ "
          "nghiêm trọng."),
    ("tbl", [["Ngưỡng", "Người lạ lọt qua (FAR)", "Người quen bị từ chối (FRR)"],
             ["0,55 — đang dùng", "25,7 %", "1,9 %"],
             ["0,60", "12,0 %", "4,3 %"],
             ["0,631 — điểm cân bằng lỗi", "5,5 %", "6,0 %"],
             ["0,65", "4,2 %", "7,4 %"],
             ["0,68 — chọn dùng", "2,1 %", "10,9 %"],
             ["0,70", "1,5 %", "13,8 %"],
             ["0,75", "0,2 %", "25,8 %"]]),
    ("cap", "Bảng 3.23. Đánh đổi giữa nhận nhầm và từ chối oan theo ngưỡng"),
    ("p", "Ngưỡng 0,55 cho **một phần tư số người lạ đi qua**. Với một hệ thống điểm danh "
          "thì con số đó phá hỏng chính lý do nó tồn tại."),
    ("p", "Điểm cân bằng lỗi (0,631, nơi FAR bằng FRR) là lựa chọn mặc định khi hai loại "
          "lỗi ngang giá. Ở đây chúng **không ngang giá**: nhận nhầm thì ghi sai vào sổ, "
          "người vắng thành có mặt, và không ai phát hiện ra; còn từ chối oan thì người "
          "dùng chỉ cần đứng lại một lần nữa, phiền nhưng tự phục hồi được và họ biết "
          "ngay là có chuyện. Coi nhận nhầm nặng gấp ba lần từ chối oan thì tổng lỗi nhỏ "
          "nhất rơi vào **0,68** — đây là ngưỡng được chọn."),

    ("p", "**Lỗi 7 — vết bị tiêu thụ khi còn đang chờ xác minh.** Đây là lỗi tinh vi nhất "
          "trong tám lỗi, và là lỗi do chính việc thêm tầng chống giả mạo tạo ra."),
    ("p", "Bộ bám vết đánh dấu một vết là \"đã phát sự kiện\" ngay tại thời điểm trả nó "
          "ra. Đoạn mã kiểm tra điểm sống lại được đặt **sau** lời gọi đó, nên khi điểm "
          "sống còn là \"đang đo\" thì vòng lặp bỏ qua — và vết mất quyền phát vĩnh viễn. "
          "Trình tự thực tế: người bước vào, vết đủ số phiếu và được xác nhận sau khoảng "
          "0,2 giây, nhưng đo chớp mắt cần vài giây; đến khi người ấy chớp mắt và điểm "
          "sống lên 1,00 thì vết đã cháy từ lâu."),
    ("p", "Gốc rễ là hai tầng chạy ở **hai nhịp thời gian khác nhau** — nhận diện chốt "
          "sau 0,2 giây, chống giả mạo cần vài giây — mà mã nguồn nối chúng như thể chúng "
          "cùng nhịp. Cách sửa: vết chỉ bị tiêu thụ khi **thực sự gửi được gì đó đi**."),
    ("p", "Biểu hiện của lỗi này đáng chú ý về mặt phương pháp: **không có thông báo lỗi, "
          "không có ngoại lệ, không có gì trên màn hình gợi ý**. Mọi bộ phận đều báo cáo "
          "rằng nó làm đúng phần việc của mình — nhận diện đúng tên, chống giả mạo cho "
          "điểm tối đa — và chỉ chỗ nối giữa chúng là hỏng."),

    ("p", "**Lỗi 8 — tỉ lệ chuyên cần chia sai đơn vị.** Bảng điều khiển web hiện **tỉ "
          "lệ chuyên cần 133 %**. Hàm tổng hợp số liệu chia số **bản ghi** điểm danh cho "
          "số **người** đã đăng ký. Hai đại lượng này bằng nhau khi mỗi người dự đúng một "
          "ca, nhưng lệch ngay khi một người dự hai ca trong cùng ngày: ba người đăng ký, "
          "hai người mỗi người dự hai ca, thành bốn bản ghi — và 4 chia 3 ra 133 %."),
    ("p", "Dấu hiệu của lỗi đã nằm sẵn trong chính đoạn mã đó: số người vắng được tính "
          "bằng `max(0, số người − số bản ghi)`. Cái `max(0, ...)` tồn tại vì hiệu số ấy "
          "có thể âm, mà một hiệu số giữa hai lượng người thì không bao giờ được phép âm. "
          "Người viết đã **chặn triệu chứng thay vì hỏi vì sao triệu chứng xuất hiện** — "
          "và nhờ chặn được số vắng, lỗi chỉ còn lộ ra ở ô tỉ lệ phần trăm."),
    ("p", "Cách sửa là gộp bản ghi theo người trước khi đếm. Kèm theo đó, ba đẳng thức "
          "được đưa thành phép thử để các con số không thể mâu thuẫn nhau về sau: đúng "
          "giờ cộng đi muộn bằng số đã điểm danh, số đã điểm danh cộng số vắng bằng số đã "
          "đăng ký, và tỉ lệ không bao giờ vượt quá 100 %."),
    ("p", "Lỗi này đáng chú ý vì lý do nó lọt lưới: **mọi bộ kiểm thử cũ đều dựng dữ liệu "
          "một người một ca**. Trong loại dữ liệu đó, đếm bản ghi và đếm người cho ra "
          "cùng một con số, nên phép chia sai vẫn qua được tất cả. Dữ liệu kiểm thử quá "
          "đều đã che mất lỗi, chứ không phải bộ kiểm thử quá ít."),

    ("h3", "3.1.17. Bốn bài học về phương pháp kiểm thử"),
    ("p", "**Thứ nhất: phép đo tĩnh không thay thế được thao tác chuyển tiếp.** Kết quả "
          "ACER 0 % ở mục 3.1.9 đúng với quy trình đo của nó — ngồi yên ghi 60 khung hình "
          "thật, rồi giơ điện thoại ghi 60 khung giả. Nhưng nó **không bao gồm thao tác "
          "chuyển tiếp** giữa hai trạng thái, mà chính khe hở ở chỗ chuyển tiếp mới là "
          "nơi lỗi 3 và lỗi 7 sinh sống."),
    ("p", "**Thứ hai: ngưỡng hiệu chỉnh trên dữ liệu chuẩn thường sai trên dữ liệu thật.** "
          "Ba lần trong đề tài này, một ngưỡng lấy từ tài liệu hoặc chỉnh trên bộ dữ liệu "
          "chuẩn tỏ ra sai khi gặp webcam thật: ngưỡng độ nét, ngưỡng EAR, và ngưỡng nhận "
          "diện. Cả ba lần cách sửa đều giống nhau — đo lại trên dữ liệu thật rồi chọn "
          "bằng số liệu, không chọn bằng cảm tính."),
    ("p", "**Thứ ba: lỗi ở chỗ nối không hiện ra trong kiểm thử từng tầng.** Vào thời điểm "
          "tám lỗi trên còn tồn tại, hệ thống có sáu bộ kiểm thử tự động với 73 phép "
          "thử — bộ thứ bảy ở Bảng 3.19 chính là kết quả của việc sửa lỗi 8 nên chưa có "
          "lúc đó — và cả 73 phép thử đều xanh suốt thời gian ấy. Chúng kiểm tra từng tầng riêng và kiểm tra rất kỹ, nhưng không bộ nào đặt "
          "câu hỏi \"điều gì xảy ra khi tầng A kết luận sau 0,2 giây còn tầng B cần 5 "
          "giây\". Sau khi phát hiện, nhóm bổ sung một bộ kiểm thử riêng cho chỗ nối đó, "
          "trong đó có một phép thử **tái hiện đúng lỗi cũ** để chứng minh bài kiểm thử "
          "thật sự bắt được nó chứ không phải một bài luôn cho kết quả xanh."),
    ("p", "**Thứ tư, rút ra từ lỗi 8: dữ liệu kiểm thử quá đều cũng che được lỗi.** Bảy "
          "lỗi đầu lọt lưới vì bộ kiểm thử không hỏi đúng câu hỏi. Lỗi thứ tám lọt lưới "
          "vì lý do khác hẳn: câu hỏi thì đúng — mọi bộ đều kiểm tra số liệu tổng hợp — "
          "nhưng **dữ liệu dựng lên để kiểm tra lại quá đều**, mỗi người đúng một ca. "
          "Trong dữ liệu đó, phép chia sai và phép chia đúng cho cùng một kết quả. Thêm "
          "phép thử vào một bộ dữ liệu đều như vậy cũng không bắt được lỗi; phải thay đổi "
          "**hình dạng** của dữ liệu. Bộ kiểm thử mới vì thế dựng hẳn trường hợp một "
          "người dự hai ca, và giữ lại cả trường hợp một người một ca để chứng minh bản "
          "sửa không làm sai lệch tình huống thường gặp."),
]
