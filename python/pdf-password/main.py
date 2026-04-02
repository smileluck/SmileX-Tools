import subprocess
import os

# 获取脚本所在目录并切换到该目录执行
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)


PDF_FILE = "input.pdf"
HASH_FILE = "hash.txt"


def extract_hash():
    """
    使用 pdf2john 提取 PDF hash
    """
    print("[*] Extracting hash from PDF...")

    cmd = f"python pdf2john.py {PDF_FILE} > {HASH_FILE}"
    result = subprocess.run(cmd, shell=True)

    if not os.path.exists(HASH_FILE):
        raise Exception("[-] Failed to generate hash.txt")

    print("[+] Hash extracted!")


def run_hashcat():
    """
    使用 Hashcat 进行 mask 破解
    已知：
        6位数字
        前缀：60 / 00 / 30
    """
    print("[*] Running Hashcat...")

    prefixes = ["60", "00", "30"]

    for prefix in prefixes:
        mask = f"{prefix}?d?d?d?d"

        print(f"[+] Trying mask: {mask}")

        cmd = [
            "hashcat",
            "-a", "3",          # mask attack
            "-m", "10500",     # PDF hash 模式
            HASH_FILE,
            mask,
            "-O",              # 优化
            "-w", "3",         # 性能模式
            "--quiet"
        ]

        subprocess.run(cmd)


PASSWORD_FILE = "password.txt"


def get_result():
    """
    获取破解结果并提取密码
    """
    print("[*] Checking result...")

    result = subprocess.run(
        ["hashcat", "--show", HASH_FILE],
        capture_output=True,
        text=True
    )

    output = result.stdout.strip()

    if output:
        print("[+] Password found!")
        parts = output.split(":")
        if len(parts) >= 2:
            password = parts[-1]
            print(f"[+] Password: {password}")
            return password
        print(output)
    else:
        print("[-] Password not found")
    return None


def main():
    extract_hash()
    run_hashcat()
    get_result()


if __name__ == "__main__":
    main()