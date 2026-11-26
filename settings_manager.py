#!/usr/bin/env python3
"""
مدیریت فایل تنظیمات aqsettings.txt
این برنامه فایل settings را خوانده، رمزگشایی می‌کند، تغییرات را اعمال کرده و دوباره رمزنگاری می‌کند.

استفاده:
  python3 settings_manager.py read <input_file>           # خواندن و نمایش تنظیمات
  python3 settings_manager.py write <input_file> <json>   # نوشتن تنظیمات جدید
  python3 settings_manager.py encrypt <json_file> <output_file>  # رمزنگاری JSON به فایل
  python3 settings_manager.py decrypt <input_file>        # رمزگشایی و نمایش JSON

مثال:
  python3 settings_manager.py read aqsettings.txt
  python3 settings_manager.py write aqsettings.txt '{"hours":12,"rules":{"stag":{"on":true,"wind":5,"blh":200}}}'
  
برای استفاده در GitHub Actions:
  - فایل settings.json را در Secrets بگذارید
  - در workflow آن را decrypt کرده و در repository قرار دهید
"""

import sys
import json
import base64
import os


def xor_cipher(data: bytes, key: str) -> bytes:
    """رمزنگاری/رمزگشایی XOR با کلید"""
    key_bytes = key.encode('utf-8')
    key_len = len(key_bytes)
    return bytes(b ^ key_bytes[i % key_len] for i, b in enumerate(data))


def decode_settings(encoded: str, key: str = 'aq#Qm-9x') -> dict:
    """رمزگشایی فایل تنظیمات"""
    try:
        # حذف whitespace
        encoded = encoded.strip()
        
        # Base64 decode
        encrypted = base64.b64decode(encoded)
        
        # XOR decrypt
        decrypted = xor_cipher(encrypted, key)
        
        # JSON parse
        settings = json.loads(decrypted.decode('utf-8'))
        
        return settings
    except Exception as e:
        raise ValueError(f"خطا در رمزگشایی: {e}")


def encode_settings(settings: dict, key: str = 'aq#Qm-9x') -> str:
    """رمزنگاری تنظیمات به فرمت فایل"""
    try:
        # JSON stringify (بدون فاصله اضافی)
        json_str = json.dumps(settings, ensure_ascii=False, separators=(',', ':'))
        json_bytes = json_str.encode('utf-8')
        
        # XOR encrypt
        encrypted = xor_cipher(json_bytes, key)
        
        # Base64 encode
        encoded = base64.b64encode(encrypted).decode('ascii')
        
        return encoded
    except Exception as e:
        raise ValueError(f"خطا در رمزنگاری: {e}")


def validate_settings(settings: dict) -> bool:
    """اعتبارسنجی ساختار تنظیمات"""
    if not isinstance(settings, dict):
        raise ValueError("تنظیمات باید یک object باشد")
    
    if 'hours' not in settings:
        raise ValueError("فیلد 'hours' الزامی است")
    
    hours = settings['hours']
    if not isinstance(hours, int) or hours < 1 or hours > 72:
        raise ValueError("hours باید عددی بین 1 تا 72 باشد")
    
    if 'rules' not in settings:
        raise ValueError("فیلد 'rules' الزامی است")
    
    rules = settings['rules']
    if not isinstance(rules, dict):
        raise ValueError("rules باید یک object باشد")
    
    # بررسی ساختار rules (اختیاری، می‌توانید بیشتر اضافه کنید)
    for key in ['stag', 'season', 'qom', 'qan', 'pf', 'wash']:
        if key in rules and not isinstance(rules[key], dict):
            raise ValueError(f"rules.{key} باید یک object باشد")
    
    return True


def cmd_read(input_file: str):
    """خواندن و نمایش تنظیمات"""
    if not os.path.exists(input_file):
        print(f"❌ فایل یافت نشد: {input_file}", file=sys.stderr)
        sys.exit(1)
    
    with open(input_file, 'r', encoding='utf-8') as f:
        encoded = f.read()
    
    try:
        settings = decode_settings(encoded)
        print(json.dumps(settings, ensure_ascii=False, indent=2))
        return settings
    except Exception as e:
        print(f"❌ خطا: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_write(input_file: str, json_data: str):
    """نوشتن تنظیمات جدید"""
    try:
        settings = json.loads(json_data)
    except json.JSONDecodeError as e:
        print(f"❌ JSON نامعتبر: {e}", file=sys.stderr)
        sys.exit(1)
    
    try:
        validate_settings(settings)
    except ValueError as e:
        print(f"❌ تنظیمات نامعتبر: {e}", file=sys.stderr)
        sys.exit(1)
    
    try:
        encoded = encode_settings(settings)
        
        # پشتیبان‌گیری از فایل قبلی
        if os.path.exists(input_file):
            backup = input_file + '.backup'
            with open(input_file, 'r', encoding='utf-8') as src:
                with open(backup, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
            print(f"✓ نسخه پشتیبان: {backup}")
        
        # نوشتن فایل جدید
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write(encoded)
        
        print(f"✓ فایل با موفقیت نوشته شد: {input_file}")
        
    except Exception as e:
        print(f"❌ خطا: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_encrypt(json_file: str, output_file: str):
    """رمزنگاری JSON به فایل"""
    if not os.path.exists(json_file):
        print(f"❌ فایل یافت نشد: {json_file}", file=sys.stderr)
        sys.exit(1)
    
    with open(json_file, 'r', encoding='utf-8') as f:
        try:
            settings = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ JSON نامعتبر: {e}", file=sys.stderr)
            sys.exit(1)
    
    try:
        validate_settings(settings)
    except ValueError as e:
        print(f"❌ تنظیمات نامعتبر: {e}", file=sys.stderr)
        sys.exit(1)
    
    try:
        encoded = encode_settings(settings)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(encoded)
        
        print(f"✓ فایل رمزنگاری شد: {output_file}")
        
    except Exception as e:
        print(f"❌ خطا: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_decrypt(input_file: str):
    """رمزگشایی فایل و نمایش JSON"""
    return cmd_read(input_file)


def show_usage():
    """نمایش راهنمای استفاده"""
    print("""
استفاده:
  python3 settings_manager.py read <input_file>
  python3 settings_manager.py write <input_file> <json_string>
  python3 settings_manager.py encrypt <json_file> <output_file>
  python3 settings_manager.py decrypt <input_file>

مثال‌ها:
  # خواندن تنظیمات
  python3 settings_manager.py read aqsettings.txt

  # نوشتن تنظیمات جدید
  python3 settings_manager.py write aqsettings.txt '{"hours":12,"rules":{"stag":{"on":true,"wind":5,"blh":200}}}'

  # رمزنگاری از JSON
  python3 settings_manager.py encrypt settings.json aqsettings.txt

  # رمزگشایی
  python3 settings_manager.py decrypt aqsettings.txt
""")


def main():
    if len(sys.argv) < 2:
        show_usage()
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'read' and len(sys.argv) == 3:
        cmd_read(sys.argv[2])
    
    elif command == 'write' and len(sys.argv) == 4:
        cmd_write(sys.argv[2], sys.argv[3])
    
    elif command == 'encrypt' and len(sys.argv) == 4:
        cmd_encrypt(sys.argv[2], sys.argv[3])
    
    elif command == 'decrypt' and len(sys.argv) == 3:
        cmd_decrypt(sys.argv[2])
    
    else:
        show_usage()
        sys.exit(1)


if __name__ == '__main__':
    main()
