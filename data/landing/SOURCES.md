# Corpus sources

## Topic

University undergraduate training regulations in Vietnam (quy chế đào tạo trình độ đại học).

The corpus contains official university regulations and public pages describing rules for credits, course registration, assessment, academic standing, graduation, and related training procedures. Sources were checked on 2026-09-20.

## Legal and policy documents

1. **Quy chế đào tạo của Đại học Bách khoa Hà Nội - Quyết định 5445/QĐ-ĐHBK (2025)**  
   Local file: `legal/QCDT_2025_5445_QD-DHBK.pdf`  
   Official URL: <https://ctt.hust.edu.vn/Upload/Nguy%E1%BB%85n%20Qu%E1%BB%91c%20%C4%90%E1%BA%A1t/files/DTDH_QDQC/Hoctap/QCDT_2025_5445_QD-DHBK.pdf>

2. **Quy chế đào tạo trình độ đại học tại Trường Đại học Sư phạm Thành phố Hồ Chí Minh - Quyết định 1410/QĐ-ĐHSP (2021)**  
   Local file: `legal/quyet-dinh-ban-hanh-quy-che-dao-tao-trinh-do-dai-hoc-tai-truong-dai-hoc-su-pham-thanh-pho-ho-chi-minh-ap-dung-tu-khoa-tuyen-sinh-2021-tro-ve-sau.pdf`  
   Official URL: <https://ctsv.hcmue.edu.vn/storage/files/quyet-dinh-ban-hanh-quy-che-dao-tao-trinh-do-dai-hoc-tai-truong-dai-hoc-su-pham-thanh-pho-ho-chi-minh-ap-dung-tu-khoa-tuyen-sinh-2021-tro-ve-sau.pdf>

3. **Quy chế đào tạo trình độ đại học của Trường Đại học Thăng Long (2025)**  
   Local file: `legal/QĐ 25091102.QĐ-ĐHTL ban hành Quy chế ĐTĐH 2025.pdf`  
   Official source page: <https://thanglong.edu.vn/quyet-dinh-ban-hanh-quy-che-dao-tao-trinh-do-dai-hoc-cua-truong-dai-hoc-thang-long-21487.html>

## Public articles and pages

1. **Trường Đại học Nha Trang - Ban hành Quy chế đào tạo trình độ đại học áp dụng từ năm học 2021-2022**  
   <https://thanhnien.ntu.edu.vn/tin-tuc/ban-hanh-dao-tao-trinh-do-dai-hoc-cua-truong-dai-hoc-nha-trang-ap-dung-tu-nam-hoc>

2. **Trường Đại học Đại Nam - Quy định đào tạo đại học và cao đẳng hệ chính quy theo học chế tín chỉ**  
   <https://tuyensinh.dainam.edu.vn/vi/tin-tuc/quy-dinh-dao-tao-dai-hoc-va-cao-dang-he-chinh-quy-theo-hoc-che-tin-chi>

3. **Trường Đại học Sư phạm Hà Nội - Quy chế đào tạo đại học**  
   <https://staff.hnue.edu.vn/Daotao/DaotaoDaihoc/QuychedaotaoDaihoc.aspx>

4. **Trường Đại học Công nghiệp Thành phố Hồ Chí Minh - Quy chế đào tạo tín chỉ ban hành năm 2025**  
   <https://pdt.iuh.edu.vn/quy-che-dao-tao>

5. **Trường Đại học Văn Lang - Quy chế đào tạo**  
   <https://vhub.vlu.edu.vn/quy-che-dao-tao>

## Processing note

The Thăng Long PDF is image-only. `src/task3_convert_markdown.py` therefore uses Tesseract OCR with `vie+eng` language data when MarkItDown cannot extract text. On a new machine, install Tesseract and its Vietnamese language model before rerunning the conversion. OCR output should be spot-checked against the scan, especially handwritten decision numbers, dates, stamps, and table cells.
