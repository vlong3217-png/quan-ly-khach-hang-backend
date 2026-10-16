"""
Vietnamese number to words converter (S7-05 AC 1).
Chuyển đổi số tiền thành chữ tiếng Việt chuẩn hóa cho báo giá và hợp đồng.
"""

from typing import List


DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
UNITS = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ"]


def _read_three_digits(number: int, has_higher_group: bool) -> List[str]:
    """Đọc nhóm 3 chữ số."""
    words = []
    c = number // 100
    h = (number % 100) // 10
    d = number % 10

    if c > 0 or has_higher_group:
        words.append(DIGITS[c])
        words.append("trăm")

    if h > 1:
        words.append(DIGITS[h])
        words.append("mươi")
        if d == 1:
            words.append("mốt")
        elif d == 5:
            words.append("lăm")
        elif d > 0:
            words.append(DIGITS[d])
    elif h == 1:
        words.append("mười")
        if d == 1:
            words.append("một")
        elif d == 5:
            words.append("lăm")
        elif d > 0:
            words.append(DIGITS[d])
    else:  # h == 0
        if (c > 0 or has_higher_group) and d > 0:
            words.append("lẻ")
            words.append(DIGITS[d])
        elif d > 0:
            words.append(DIGITS[d])

    return words


def number_to_vietnamese_words(amount: float, suffix: str = "đồng chẵn") -> str:
    """
    Chuyển đổi số tiền thành chữ tiếng Việt.
    Ví dụ:
        59400000 -> "Năm mươi chín triệu bốn trăm nghìn đồng chẵn"
        1500000 -> "Một triệu năm trăm nghìn đồng chẵn"
        1005 -> "Một nghìn không trăm lẻ năm đồng chẵn"
    """
    if amount is None or amount == 0:
        return "Không đồng"

    # Làm tròn số tiền nguyên
    int_val = int(round(amount))
    if int_val < 0:
        return "Âm " + number_to_vietnamese_words(abs(int_val), suffix=suffix).lower()

    if int_val == 0:
        return "Không đồng"

    # Chia thành các nhóm 3 chữ số từ phải sang trái
    groups = []
    temp = int_val
    while temp > 0:
        groups.append(temp % 1000)
        temp //= 1000

    words = []
    num_groups = len(groups)

    for i in range(num_groups - 1, -1, -1):
        grp_val = groups[i]
        if grp_val > 0:
            has_higher = (i < num_groups - 1)
            grp_words = _read_three_digits(grp_val, has_higher)
            words.extend(grp_words)
            unit_name = UNITS[i % len(UNITS)]
            if unit_name:
                words.append(unit_name)

    result_str = " ".join(words).strip()
    if suffix:
        result_str += " " + suffix.strip()

    # Viết hoa chữ cái đầu tiên
    if result_str:
        result_str = result_str[0].upper() + result_str[1:]

    return result_str
