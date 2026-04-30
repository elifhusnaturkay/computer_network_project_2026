"""
client.py
---------
TCP Chat İstemcisi / TCP Chat Client

Çalıştırmak için / To run:
  python3 client.py

Her terminal penceresinde ayrı bir client çalıştırın.
Run a separate client in each terminal window.

Komutlar / Commands:
  (sadece yaz)             Herkese mesaj / Message to everyone
  /users                   Online kullanıcıları listele / List online users
  /group create <ad>       Grup oluştur / Create a group
  /group join <ad>         Gruba katıl / Join a group
  /group leave <ad>        Gruptan ayrıl / Leave a group
  /groups                  Grupları listele / List all groups
  /gmsg <grup> <mesaj>     Gruba mesaj / Send to group
  /help                    Yardım / Show help
  /quit                    Çıkış / Disconnect
"""

import socket
import threading
from protocol import make_message, send_msg, recv_msg

# ── Bağlantı ayarları / Connection settings ────────────────────────────────
HOST = "127.0.0.1"   # Sunucu adresi / Server address
PORT = 5050          # Sunucu portu / Server port

# ── Global bayrak / Global flag ────────────────────────────────────────────
# False yapıldığında hem alıcı hem gönderici döngü durur
# When set to False, both receive and send loops stop
running = True


# ── Yardım metni / Help text ───────────────────────────────────────────────

def print_help() -> None:
    """Kullanılabilir komutları ekrana yazar. / Prints available commands."""
    print("\n─── Komutlar / Commands ───────────────────────────────")
    print("  (metin yaz)              Herkese mesaj gönder / Send to everyone")
    print("  /users                   Online kullanıcıları listele / List online users")
    print("  /group create <ad>       Grup oluştur / Create a group")
    print("  /group join <ad>         Gruba katıl / Join a group")
    print("  /group leave <ad>        Gruptan ayrıl / Leave a group")
    print("  /groups                  Grupları listele / List all groups")
    print("  /gmsg <grup> <mesaj>     Gruba mesaj gönder / Send to group")
    print("  /help                    Bu yardımı göster / Show this help")
    print("  /quit                    Bağlantıyı kes / Disconnect")
    print("───────────────────────────────────────────────────────\n")


# ── Alıcı döngüsü / Receive loop ──────────────────────────────────────────

def receive_loop(file_obj) -> None:
    """
    Sunucudan gelen mesajları sürekli dinler ve ekrana yazar.
    Continuously listens for messages from the server and prints them.

    Ayrı bir thread'de çalışır / Runs in a separate thread.
    """
    global running

    while running:
        try:
            msg = recv_msg(file_obj)

            # Bağlantı kapandı / Connection closed
            if msg is None:
                if running:
                    print("\nSunucudan bağlantı kesildi. / Disconnected from server.")
                    running = False
                break

            msg_type = msg.get("type")
            sender = msg.get("sender", "?")
            data = msg.get("data", {})

            # ── Genel sohbet mesajı / General chat message ─────────────────
            if msg_type == "chat":
                print(f"\n[Genel / General] {sender}: {data.get('message', '')}")

            # ── Grup mesajı / Group message ────────────────────────────────
            elif msg_type == "group_msg":
                group = data.get("group_name", "?")
                print(f"\n[Grup / Group: {group}] {sender}: {data.get('message', '')}")

            # ── Online kullanıcı listesi / Online user list ─────────────────
            elif msg_type == "user_list":
                users = data.get("users", [])
                print(f"\nOnline kullanıcılar / Online users: {', '.join(users)}")

            # ── Grup listesi / Group list ───────────────────────────────────
            elif msg_type == "group_list":
                group_info = data.get("groups", {})
                if not group_info:
                    print("\nHiç grup yok. / No groups available.")
                else:
                    print("\n─── Gruplar / Groups ───")
                    for gname, members in group_info.items():
                        print(f"  {gname}: {', '.join(members)}")
                    print("───────────────────────")

            # ── Bilgi mesajı / Info message (sunucudan / from server) ───────
            elif msg_type == "info":
                print(f"\n[Bilgi / Info] {data.get('message', '')}")

            # ── Hata mesajı / Error message ─────────────────────────────────
            elif msg_type == "error":
                print(f"\n[Hata / Error] {data.get('message', '')}")

        except Exception:
            # Beklenmedik hata ya da bağlantı kesildi
            # Unexpected error or connection dropped
            if running:
                print("\nBağlantı kesildi. / Connection lost.")
                running = False
            break


# ── Giriş döngüsü / Input loop ────────────────────────────────────────────

def input_loop(sock, username):
    """
    Kullanıcıdan girdi alır ve uygun mesajı sunucuya gönderir.
    Reads user input and sends the appropriate message to the server.

    Ana thread'de çalışır / Runs in the main thread.
    """
    global running

    while running:
        try:
            text = input("")
        except (EOFError, KeyboardInterrupt):
            # Ctrl+C ya da EOF → çıkış / Ctrl+C or EOF → exit
            running = False
            break

        text = text.strip()
        if not text:
            continue  # Boş satırı geç / Skip empty lines

        # ── Çıkış / Quit ───────────────────────────────────────────────────
        if text == "/quit":
            running = False
            break

        # ── Yardım / Help ──────────────────────────────────────────────────
        elif text == "/help":
            print_help()

        # ── Online kullanıcılar / Online users ─────────────────────────────
        elif text == "/users":
            send_msg(sock, make_message("users", username, {}))

        # ── Grupları listele / List groups ─────────────────────────────────
        elif text == "/groups":
            send_msg(sock, make_message("groups", username, {}))

        # ── Grup komutları / Group commands ────────────────────────────────
        elif text.startswith("/group "):
            # Komutu parçalara ayır / Split the command into parts
            parts = text.split(" ", 2)   # ["/group", "<action>", "<name?>"]
            if len(parts) < 2:
                print("Kullanım / Usage: /group create|join|leave <ad/name>")
                continue

            action = parts[1]

            if action in ("create", "join", "leave"):
                if len(parts) < 3 or not parts[2].strip():
                    print(f"Kullanım / Usage: /group {action} <grup_adı/group_name>")
                    continue
                group_name = parts[2].strip()

                if action == "create":
                    send_msg(sock, make_message("group_create", username, {"group_name": group_name}))
                elif action == "join":
                    send_msg(sock, make_message("group_join", username, {"group_name": group_name}))
                elif action == "leave":
                    send_msg(sock, make_message("group_leave", username, {"group_name": group_name}))
            else:
                print("Geçersiz grup komutu / Invalid group command: create | join | leave")

        # ── Gruba mesaj / Group message ────────────────────────────────────
        elif text.startswith("/gmsg "):
            # "/gmsg <grup> <mesaj>" → en az 3 parça gerekli
            # "/gmsg <group> <message>" → at least 3 parts required
            parts = text.split(" ", 2)
            if len(parts) < 3:
                print("Kullanım / Usage: /gmsg <grup/group> <mesaj/message>")
                continue
            group_name = parts[1]
            message = parts[2]
            send_msg(sock, make_message("group_msg", username,
                                        {"group_name": group_name, "message": message}))
            # Göndereni de kendi mesajını göster / Echo sender's own message
            print(f"[Grup / Group: {group_name}] (siz/you): {message}")

        # ── Bilinmeyen komut / Unknown command ──────────────────────────────
        elif text.startswith("/"):
            print(f"Bilinmeyen komut / Unknown command: {text}  (Yardım için / For help: /help)")

        # ── Genel mesaj / General chat message ─────────────────────────────
        else:
            send_msg(sock, make_message("chat", username, {"message": text}))
            # Göndereni de kendi mesajını göster / Echo sender's own message
            print(f"[Genel / General] (siz/you): {text}")


# ── Ana fonksiyon / Main function ───────────────────────────────────────────

def main():
    global running

    # ── Sunucuya bağlan / Connect to server ────────────────────────────────
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)  # Bağlantı zaman aşımı / Connection timeout

    try:
        sock.connect((HOST, PORT))
    except (ConnectionRefusedError, socket.timeout, OSError) as e:
        print(f"Sunucuya bağlanılamadı / Could not connect to server: {e}")
        print("Önce sunucuyu başlatın. / Make sure the server is running.")
        return

    # Bağlandıktan sonra zaman aşımını kaldır / Remove timeout after connecting
    sock.settimeout(None)
    print(f"{HOST}:{PORT} adresine bağlandı. / Connected to {HOST}:{PORT}")

    # Socketi metin modunda okumak için dosya nesnesi oluştur
    # Create a file object to read from the socket in text mode
    file_obj = sock.makefile("r", encoding="utf-8")

    # ── Kullanıcı adı gir / Enter username ────────────────────────────────
    while True:
        try:
            username = input("Kullanıcı adınız / Your username: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nİptal edildi. / Cancelled.")
            sock.close()
            return

        if not username:
            print("Kullanıcı adı boş olamaz. / Username cannot be empty.")
            continue

        # Kullanıcı adını sunucuya gönder / Send username to server
        send_msg(sock, make_message("join", username, {"username": username}))

        # Sunucudan yanıt bekle (info = kabul, error = reddedildi)
        # Wait for server response (info = accepted, error = rejected)
        try:
            response = recv_msg(file_obj)
        except Exception as e:
            print(f"Sunucu yanıtı alınamadı / Failed to read server response: {e}")
            sock.close()
            return

        if response is None:
            print("Sunucu bağlantıyı kapattı. / Server closed the connection.")
            sock.close()
            return

        if response.get("type") == "error":
            # Kullanıcı adı alınamadı, tekrar dene / Username rejected, try again
            print(f"[Hata / Error] {response['data'].get('message', '')}")
            continue

        # Kabul edildi / Accepted
        print(f"[Bilgi / Info] {response['data'].get('message', '')}")
        break

    print_help()

    # ── Alıcı thread'i başlat / Start receiver thread ──────────────────────
    recv_thread = threading.Thread(target=receive_loop, args=(file_obj,), daemon=True)
    recv_thread.start()

    # ── Giriş döngüsünü ana thread'de çalıştır / Run input loop on main thread
    try:
        input_loop(sock, username)
    except KeyboardInterrupt:
        pass

    # ── Temizlik / Cleanup ─────────────────────────────────────────────────
    running = False
    try:
        sock.close()
    except OSError:
        pass

    print("Bağlantı kesildi. / Disconnected.")


if __name__ == "__main__":
    main()
