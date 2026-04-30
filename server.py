"""
server.py
---------
TCP Chat Sunucusu / TCP Chat Server

Çalıştırmak için / To run:
  python3 server.py

Sunucu tek çalışır; birden fazla client aynı anda bağlanabilir.
One server runs; multiple clients can connect at the same time.

Adım 1: Temel yayın (broadcast) - Step 1: Basic broadcast
Adım 2: Çoklu client desteği - Step 2: Multi-client support
Adım 3: Grup desteği - Step 3: Group chat support
"""

import socket
import threading
from protocol import make_message, send_msg, recv_msg

# ── Sunucu ayarları / Server settings ──────────────────────────────────────
HOST = "127.0.0.1"   # Yerel ağ / Localhost
PORT = 5050          # Dinlenecek port / Port to listen on

# ── Paylaşılan durum / Shared state ────────────────────────────────────────
# Bağlı clientlar: { kullanıcı_adı: soket } / Connected clients: { username: socket }
clients = {}  # { username: socket }

# Gruplar: { grup_adı: {kullanıcı_adı, ...} } / Groups: { group_name: {username, ...} }
groups = {}  # { group_name: set(usernames) }

# Thread güvenliği için kilit / Lock for thread safety
lock = threading.Lock()


# ── Yardımcı fonksiyonlar / Helper functions ────────────────────────────────

def broadcast(msg, exclude=None):
    """
    Tüm bağlı clientlara mesaj gönderir (isteğe bağlı olarak birini hariç tutar).
    Sends a message to all connected clients (optionally excluding one).

    exclude: Bu kullanıcıya gönderilmez (genellikle gönderen kendisi).
    exclude: Message is not sent to this user (usually the sender).
    """
    with lock:
        for uname, sock in clients.items():
            if uname != exclude:
                try:
                    send_msg(sock, msg)
                except OSError:
                    # Gönderim başarısız olursa sessizce geç / Skip silently on send failure
                    pass


def send_to_user(username, msg):
    """
    Belirli bir kullanıcıya mesaj gönderir.
    Sends a message to a specific user.

    Kullanıcı çevrimiçiyse True, değilse False döner.
    Returns True if user is online, False otherwise.
    """
    with lock:
        if username in clients:
            try:
                send_msg(clients[username], msg)
                return True
            except OSError:
                return False
    return False


def send_to_group(group_name, msg, exclude=None):
    """
    Gruptaki tüm üyelere mesaj gönderir (isteğe bağlı olarak birini hariç tutar).
    Sends a message to all members of a group (optionally excluding one).
    """
    with lock:
        members = list(groups.get(group_name, set()))

    # Kilit dışında gönder; send_to_user kendi kilidini yönetir
    # Send outside lock; send_to_user manages its own lock
    for member in members:
        if member != exclude:
            send_to_user(member, msg)


# ── Client işleyici / Client handler ────────────────────────────────────────

def handle_client(conn, addr):
    """
    Her bağlanan client için ayrı bir thread'de çalışır.
    Runs in a separate thread for each connected client.

    Kullanıcı adı alınır, ardından mesaj döngüsü başlatılır.
    Receives the username, then starts the message loop.
    """
    # Socketi metin modunda okumak için dosya nesnesi oluştur
    # Create a file object to read from the socket in text mode
    file_obj = conn.makefile("r", encoding="utf-8")
    username = None

    try:
        # ── 1. Kullanıcı adı al / Receive username ──────────────────────────
        # İlk mesaj her zaman "join" türündedir
        # The first message is always of type "join"
        msg = recv_msg(file_obj)
        if msg is None or msg.get("type") != "join":
            conn.close()
            return

        requested_name = msg["data"].get("username", "").strip()

        # Kullanıcı adı boş veya zaten kullanılıyorsa reddet
        # Reject if username is empty or already taken
        with lock:
            if not requested_name or requested_name in clients:
                send_msg(conn, make_message("error", "server",
                                            {"message": "Kullanıcı adı geçersiz veya zaten kullanımda. / Username invalid or already taken."}))
                conn.close()
                return

            username = requested_name
            clients[username] = conn

        print(f"[+] {username} bağlandı / connected  ({addr})")

        # Hoş geldin mesajı gönder / Send welcome message to the new user
        send_msg(conn, make_message("info", "server",
                                    {"message": f"Hoş geldin {username}! / Welcome {username}!"}))

        # Diğer clientlara duyur / Announce to other clients (Step 1 & 2)
        broadcast(make_message("info", "server",
                               {"message": f"{username} sohbete katıldı. / joined the chat."}),
                  exclude=username)

        # ── 2. Mesaj döngüsü / Message loop ────────────────────────────────
        while True:
            msg = recv_msg(file_obj)
            if msg is None:
                # Bağlantı kapandı / Connection closed
                break

            msg_type = msg.get("type")

            # ── Genel mesaj / General broadcast (Step 1 & 2) ───────────────
            if msg_type == "chat":
                text = msg["data"].get("message", "")
                out = make_message("chat", username, {"message": text})
                # Gönderen hariç herkese ilet / Forward to everyone except sender
                broadcast(out, exclude=username)

            # ── Grup oluştur / Create group (Step 3) ───────────────────────
            elif msg_type == "group_create":
                group_name = msg["data"].get("group_name", "").strip()
                with lock:
                    if not group_name:
                        send_msg(conn, make_message("error", "server",
                                                    {"message": "Grup adı boş olamaz. / Group name cannot be empty."}))
                    elif group_name in groups:
                        send_msg(conn, make_message("error", "server",
                                                    {"message": f"'{group_name}' grubu zaten var. / Group already exists."}))
                    else:
                        # Grubu oluştur ve kurucuyu ekle / Create group and add creator
                        groups[group_name] = {username}
                        send_msg(conn, make_message("info", "server",
                                                    {"message": f"'{group_name}' grubu oluşturuldu ve katıldınız. / Group created and joined."}))

            # ── Gruba katıl / Join group (Step 3) ──────────────────────────
            elif msg_type == "group_join":
                group_name = msg["data"].get("group_name", "").strip()
                with lock:
                    if group_name not in groups:
                        send_msg(conn, make_message("error", "server",
                                                    {"message": f"'{group_name}' grubu bulunamadı. / Group not found."}))
                    elif username in groups[group_name]:
                        send_msg(conn, make_message("info", "server",
                                                    {"message": f"Zaten '{group_name}' grubundasınız. / Already in group."}))
                    else:
                        groups[group_name].add(username)
                        send_msg(conn, make_message("info", "server",
                                                    {"message": f"'{group_name}' grubuna katıldınız. / Joined group."}))

            # ── Gruptan ayrıl / Leave group (Step 3) ───────────────────────
            elif msg_type == "group_leave":
                group_name = msg["data"].get("group_name", "").strip()
                with lock:
                    if group_name not in groups or username not in groups[group_name]:
                        send_msg(conn, make_message("error", "server",
                                                    {"message": f"'{group_name}' grubunda değilsiniz. / Not in group."}))
                    else:
                        groups[group_name].discard(username)
                        # Grup boşaldıysa sil / Delete group if empty
                        if not groups[group_name]:
                            del groups[group_name]
                        send_msg(conn, make_message("info", "server",
                                                    {"message": f"'{group_name}' grubundan ayrıldınız. / Left group."}))

            # ── Gruba mesaj gönder / Send to group (Step 3) ────────────────
            elif msg_type == "group_msg":
                group_name = msg["data"].get("group_name", "").strip()
                text = msg["data"].get("message", "")

                with lock:
                    if group_name not in groups:
                        send_msg(conn, make_message("error", "server",
                                                    {"message": f"'{group_name}' grubu bulunamadı. / Group not found."}))
                        continue
                    if username not in groups[group_name]:
                        send_msg(conn, make_message("error", "server",
                                                    {"message": "Bu grubun üyesi değilsiniz. / Not a member of this group."}))
                        continue

                # Sadece grup üyelerine gönder / Send only to group members (Step 3)
                out = make_message("group_msg", username,
                                   {"group_name": group_name, "message": text})
                send_to_group(group_name, out, exclude=username)

            # ── Online kullanıcıları listele / List online users ────────────
            elif msg_type == "users":
                with lock:
                    user_list = list(clients.keys())
                send_msg(conn, make_message("user_list", "server", {"users": user_list}))

            # ── Grupları listele / List groups ──────────────────────────────
            elif msg_type == "groups":
                with lock:
                    # Her grup için üye listesi / Member list for each group
                    group_info = {gname: list(members) for gname, members in groups.items()}
                send_msg(conn, make_message("group_list", "server", {"groups": group_info}))

            else:
                # Bilinmeyen mesaj türü / Unknown message type
                send_msg(conn, make_message("error", "server",
                                            {"message": f"Bilinmeyen komut: {msg_type} / Unknown command."}))

    except Exception as e:
        # Beklenmedik hata / Unexpected error
        print(f"[!] {addr} hata / error: {e}")

    finally:
        # ── Temizlik / Cleanup ──────────────────────────────────────────────
        if username:
            with lock:
                clients.pop(username, None)
                # Kullanıcıyı tüm gruplardan çıkar / Remove user from all groups
                for gname in list(groups.keys()):
                    groups[gname].discard(username)
                    if not groups[gname]:
                        del groups[gname]

            print(f"[-] {username} ayrıldı / disconnected")
            # Diğer clientlara bildir / Notify other clients
            broadcast(make_message("info", "server",
                                   {"message": f"{username} sohbetten ayrıldı. / left the chat."}))

        file_obj.close()
        conn.close()


# ── Ana fonksiyon / Main function ───────────────────────────────────────────

def main():
    # Sunucu soketini oluştur / Create the server socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Port yeniden kullanımına izin ver (geliştirme kolaylığı için)
    # Allow port reuse (convenient for development restarts)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server.bind((HOST, PORT))
    server.listen(5)  # Maksimum 5 bekleyen bağlantı / Max 5 pending connections

    print(f"Sunucu başlatıldı / Server started  →  {HOST}:{PORT}")
    print("Durdurmak için Ctrl+C / Press Ctrl+C to stop\n")

    try:
        while True:
            # Yeni bağlantı bekle / Wait for a new connection
            conn, addr = server.accept()
            print(f"[~] Yeni bağlantı / New connection from {addr}")

            # Her client için ayrı bir thread başlat / Start a new thread per client
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()

    except KeyboardInterrupt:
        print("\nSunucu kapatılıyor... / Server shutting down...")
    finally:
        server.close()


if __name__ == "__main__":
    main()
