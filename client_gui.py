import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import requests
import socketio
import threading
import queue
from datetime import datetime
import random
import base64
from PIL import Image, ImageTk
import io

# --- Configuration & Theme ---
API_URL = "http://127.0.0.1:8000"
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

COLOR_BG_SIDEBAR = "#F5F7F9"
COLOR_BUBBLE_ME = "#5B96F7"
COLOR_BUBBLE_YOU = "#F0F2F5"
COLOR_TEXT_ME = "#FFFFFF"
COLOR_TEXT_YOU = "#000000"
COLOR_ACCENT = "#5B96F7"

# --- Backend Logic ---
class ChatClient:
    def __init__(self):
        self.sio = socketio.Client()
        self.token = None
        self.user_id = None
        self.username = None
        self.my_avatar_data = None
        self.message_queue = queue.Queue()
        
        self.sio.on('connect', self.on_connect)
        self.sio.on('disconnect', self.on_disconnect)
        self.sio.on('new_message', self.on_new_message)
        self.sio.on('new_friend_request', self.on_friend_request)

    def http_post(self, endpoint, data):
        headers = {'Authorization': f'Bearer {self.token}'} if self.token else {}
        try: return requests.post(f"{API_URL}{endpoint}", json=data, headers=headers)
        except: return None

    def http_get(self, endpoint, params=None):
        headers = {'Authorization': f'Bearer {self.token}'} if self.token else {}
        try: return requests.get(f"{API_URL}{endpoint}", headers=headers, params=params)
        except: return None

    def login(self, username, password):
        resp = self.http_post("/login", {"username": username, "password": password})
        if resp and resp.status_code == 200:
            data = resp.json()
            self.token = data['access_token']
            self.user_id = int(data['user_id'])
            self.username = data['display_name']
            self.my_avatar_data = data.get('avatar')
            return True, data
        return False, resp.json().get('error') if resp else "Connection Error"

    def register(self, payload):
        resp = self.http_post("/register", payload)
        return resp.status_code == 201 if resp else False, resp.json() if resp else {}

    def get_friends(self):
        resp = self.http_get("/friends")
        return resp.json() if resp and resp.status_code == 200 else []

    def search_users(self, query):
        resp = self.http_get("/search_users", params={'q': query})
        return resp.json() if resp and resp.status_code == 200 else []

    def send_friend_request(self, receiver_id):
        resp = self.http_post("/friend_request", {'receiver_id': receiver_id})
        return resp.status_code == 201 if resp else False, resp.json() if resp else {}

    def get_pending_requests(self):
        resp = self.http_get("/pending_requests")
        return resp.json() if resp and resp.status_code == 200 else []

    def respond_friend_request(self, sender_id, action):
        resp = self.http_post("/friend_response", {'sender_id': sender_id, 'action': action})
        return resp.status_code == 200 if resp else False

    def get_chat_history(self, other_user_id):
        resp = self.http_get(f"/chat_history/{other_user_id}")
        return resp.json() if resp and resp.status_code == 200 else []

    def send_message(self, to_user_id, content):
        self.sio.emit('send_message', {'to_user_id': to_user_id, 'content': content})

    def connect_websocket(self):
        try:
            self.sio.connect(API_URL, auth={'token': self.token})
            threading.Thread(target=self.sio.wait, daemon=True).start()
        except: pass

    def close(self):
        try: self.sio.disconnect()
        except: pass

    def on_connect(self): self.message_queue.put(('status', 'connected'))
    def on_disconnect(self): self.message_queue.put(('status', 'disconnected'))
    def on_new_message(self, data): self.message_queue.put(('new_message', data))
    def on_friend_request(self, data): self.message_queue.put(('new_request', data))

# --- UI Components ---
class Avatar(ctk.CTkFrame):
    def __init__(self, master, name, avatar_data=None, size=40, **kwargs):
        super().__init__(master, width=size, height=size, fg_color="transparent", **kwargs)
        image = None
        if avatar_data:
            try:
                img_bytes = base64.b64decode(avatar_data)
                pil_img = Image.open(io.BytesIO(img_bytes))
                pil_img = pil_img.resize((size, size), Image.Resampling.LANCZOS)
                image = ctk.CTkImage(light_image=pil_img, size=(size, size))
            except: pass

        if image:
            self.lbl = ctk.CTkLabel(self, text="", image=image)
            self.lbl.place(relx=0.5, rely=0.5, anchor="center")
        else:
            canvas = ctk.CTkCanvas(self, width=size, height=size, bg=COLOR_BG_SIDEBAR, highlightthickness=0)
            canvas.place(relx=0.5, rely=0.5, anchor="center")
            colors = ["#FF5733", "#33FF57", "#3357FF", "#F033FF", "#FF33A8"]
            fill_col = random.choice(colors)
            initial = name[0].upper() if name else "?"
            canvas.create_oval(2, 2, size-2, size-2, fill=fill_col, outline="")
            canvas.create_text(size/2, size/2, text=initial, fill="white", font=("Arial", int(size/2.5), "bold"))
            self.lbl = canvas

    def bind_click(self, command):
        self.lbl.bind("<Button-1>", command)

class FriendListItem(ctk.CTkFrame):
    def __init__(self, master, user_id, username, avatar_data, on_click, **kwargs):
        super().__init__(master, fg_color="transparent", corner_radius=0, height=60, **kwargs)
        self.user_id = user_id
        self.on_click = on_click
        self.username = username

        self.bind("<Enter>", lambda e: self.configure(fg_color="#E8E8E8"))
        self.bind("<Leave>", lambda e: self.configure(fg_color="transparent"))
        self.bind("<Button-1>", self.clicked)

        self.avatar = Avatar(self, username, avatar_data, size=40)
        self.avatar.place(x=10, y=10)
        self.avatar.bind_click(self.clicked)

        self.lbl_name = ctk.CTkLabel(self, text=username, font=("Arial", 14, "bold"), text_color="black")
        self.lbl_name.place(x=60, y=15)
        self.lbl_name.bind("<Button-1>", self.clicked)

    def clicked(self, event=None):
        self.on_click(self.user_id, self.username)

class ChatBubble(ctk.CTkFrame):
    def __init__(self, master, text, is_me, timestamp, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        bg = COLOR_BUBBLE_ME if is_me else COLOR_BUBBLE_YOU
        fg = COLOR_TEXT_ME if is_me else COLOR_TEXT_YOU
        anchor = "e" if is_me else "w"
        
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="x", padx=20, pady=5)
        self.bubble = ctk.CTkFrame(self.container, fg_color=bg, corner_radius=18)
        self.bubble.pack(anchor=anchor, ipadx=5, ipady=2)
        self.lbl = ctk.CTkLabel(self.bubble, text=text, text_color=fg, font=("Arial", 13), wraplength=400, justify="left")
        self.lbl.pack(padx=12, pady=8)
        
        try:
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime("%H:%M")
        except: time_str = ""
        self.time = ctk.CTkLabel(self.bubble, text=time_str, text_color=fg, font=("Arial", 8))
        self.time.pack(anchor="e", padx=10, pady=(0,5))

# --- Main Application ---
class ChatApp(ctk.CTk):
    def __init__(self, client_logic):
        super().__init__()
        self.client = client_logic
        self.title(f"Messenger - {self.client.username}")
        self.geometry("1100x700")
        self.configure(fg_color="white")

        self.grid_columnconfigure(0, weight=0, minsize=300)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, fg_color=COLOR_BG_SIDEBAR, width=300, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        self.side_header = ctk.CTkFrame(self.sidebar, fg_color="transparent", height=60)
        self.side_header.pack(fill="x", pady=10, padx=10)
        self.my_avatar = Avatar(self.side_header, self.client.username, self.client.my_avatar_data, size=40)
        self.my_avatar.pack(side="left")
        ctk.CTkLabel(self.side_header, text="Chats", font=("Arial", 20, "bold"), text_color="gray").pack(side="right", padx=10)

        self.search_entry = ctk.CTkEntry(self.sidebar, placeholder_text="Search users...", fg_color="white", border_width=0, height=35, corner_radius=20, text_color="black")
        self.search_entry.pack(fill="x", padx=15, pady=10)
        self.search_entry.bind("<Return>", self.on_search)

        self.tab_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.tab_frame.pack(fill="x", padx=15)
        self.btn_friends = ctk.CTkButton(self.tab_frame, text="Friends", width=130, fg_color="white", text_color="black", hover_color="#E0E0E0", command=self.show_friends)
        self.btn_friends.pack(side="left", padx=2)
        self.btn_search = ctk.CTkButton(self.tab_frame, text="Search", width=130, fg_color="transparent", text_color="gray", hover_color="#E0E0E0", command=self.show_search)
        self.btn_search.pack(side="right", padx=2)

        self.list_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.list_scroll.pack(fill="both", expand=True, padx=5, pady=10)

        # Chat Area
        self.chat_area = ctk.CTkFrame(self, fg_color="white", corner_radius=0)
        self.chat_area.grid(row=0, column=1, sticky="nsew")
        self.chat_area.grid_rowconfigure(1, weight=1)
        self.chat_area.grid_columnconfigure(0, weight=1)

        self.welcome = ctk.CTkFrame(self.chat_area, fg_color="white")
        self.welcome.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(self.welcome, text="Select a chat to start messaging", font=("Arial", 16), text_color="gray").pack()

        self.main_chat = ctk.CTkFrame(self.chat_area, fg_color="white", corner_radius=0)
        
        self.chat_header = ctk.CTkFrame(self.main_chat, fg_color="white", height=70)
        self.chat_header.pack(fill="x", side="top")
        tk.Frame(self.chat_header, height=1, bg="#E0E0E0").pack(side="bottom", fill="x")
        
        self.header_avt_frame = ctk.CTkFrame(self.chat_header, fg_color="transparent")
        self.header_avt_frame.pack(side="left", padx=20, pady=10)
        self.header_name = ctk.CTkLabel(self.chat_header, text="", font=("Arial", 18, "bold"), text_color="black")
        self.header_name.pack(side="left", pady=10)

        self.msg_scroll = ctk.CTkScrollableFrame(self.main_chat, fg_color="white")
        self.msg_scroll.pack(fill="both", expand=True)

        self.input_bar = ctk.CTkFrame(self.main_chat, fg_color="white", height=60)
        self.input_bar.pack(fill="x", side="bottom", padx=20, pady=10)
        self.entry_msg = ctk.CTkEntry(self.input_bar, placeholder_text="Type a message...", fg_color="#F0F2F5", border_width=0, height=45, corner_radius=25, text_color="black")
        self.entry_msg.pack(side="left", fill="x", expand=True, padx=(0,10))
        self.entry_msg.bind("<Return>", self.send_msg)
        ctk.CTkButton(self.input_bar, text="➤", width=45, height=45, corner_radius=25, fg_color=COLOR_ACCENT, command=self.send_msg).pack(side="right")

        self.current_pid = None
        self.mode = "friends"
        self.refresh_sidebar()
        self.process_queue()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def show_friends(self):
        self.mode = "friends"
        self.btn_friends.configure(fg_color="white", text_color="black")
        self.btn_search.configure(fg_color="transparent", text_color="gray")
        self.refresh_sidebar()

    def show_search(self):
        self.mode = "search"
        self.btn_friends.configure(fg_color="transparent", text_color="gray")
        self.btn_search.configure(fg_color="white", text_color="black")
        self.refresh_sidebar()

    def on_search(self, event=None):
        if self.mode == "friends": return
        q = self.search_entry.get()
        if not q: return
        for w in self.list_scroll.winfo_children(): w.destroy()
        res = self.client.search_users(q)
        if not res: ctk.CTkLabel(self.list_scroll, text="No users found", text_color="gray").pack(pady=20)
        for u in res:
            f = ctk.CTkFrame(self.list_scroll, fg_color="white", height=50)
            f.pack(fill="x", pady=1)
            Avatar(f, u['display_name'], u['avatar'], size=35).pack(side="left", padx=10)
            ctk.CTkLabel(f, text=u['display_name'], font=("Arial", 13, "bold"), text_color="black").pack(side="left")
            
            st = u['status']
            if st == 'none': ctk.CTkButton(f, text="Add", width=60, height=25, command=lambda i=u['id']: self.req(i)).pack(side="right", padx=10)
            elif st == 'accepted': ctk.CTkLabel(f, text="Friend", text_color="green").pack(side="right", padx=10)
            elif st == 'pending': ctk.CTkLabel(f, text="Sent", text_color="gray").pack(side="right", padx=10)
            elif st == 'incoming_request': ctk.CTkLabel(f, text="Pending", text_color="orange").pack(side="right", padx=10)

    def refresh_sidebar(self):
        if self.mode == "search": return
        for w in self.list_scroll.winfo_children(): w.destroy()
        
        reqs = self.client.get_pending_requests()
        if reqs:
            ctk.CTkLabel(self.list_scroll, text="REQUESTS", text_color=COLOR_ACCENT, font=("Arial", 10, "bold")).pack(anchor="w", padx=15, pady=5)
            for r in reqs:
                f = ctk.CTkFrame(self.list_scroll, fg_color="white")
                f.pack(fill="x", pady=1)
                Avatar(f, r['display_name'], r['avatar'], size=30).pack(side="left", padx=5)
                ctk.CTkLabel(f, text=r['display_name'], text_color="black").pack(side="left")
                ctk.CTkButton(f, text="✓", width=30, fg_color="green", command=lambda i=r['id']: self.resp(i, 'accept')).pack(side="right", padx=2)
                ctk.CTkButton(f, text="✗", width=30, fg_color="red", command=lambda i=r['id']: self.resp(i, 'reject')).pack(side="right", padx=5)

        friends = self.client.get_friends()
        if not friends: ctk.CTkLabel(self.list_scroll, text="No friends yet", text_color="gray").pack(pady=20)
        for f in friends:
            FriendListItem(self.list_scroll, f['id'], f['display_name'], f['avatar'], self.open_chat).pack(fill="x", pady=1)

    def req(self, uid):
        self.client.send_friend_request(uid)
        self.on_search()
    def resp(self, uid, act):
        self.client.respond_friend_request(uid, act)
        self.refresh_sidebar()

    def open_chat(self, uid, uname):
        self.current_pid = uid
        self.welcome.place_forget()
        self.main_chat.pack(fill="both", expand=True)
        for w in self.header_avt_frame.winfo_children(): w.destroy()
        f_list = self.client.get_friends()
        avt = None
        for f in f_list:
            if f['id'] == uid: avt = f['avatar']
        
        Avatar(self.header_avt_frame, uname, avt, size=45).pack()
        self.header_name.configure(text=uname)
        
        for w in self.msg_scroll.winfo_children(): w.destroy()
        self.msg_scroll.update()
        msgs = self.client.get_chat_history(uid)
        for m in msgs: self.add_bubble(m)
        self.after(100, self.scroll_btm)

    def send_msg(self, event=None):
        t = self.entry_msg.get()
        if t and self.current_pid:
            self.client.send_message(self.current_pid, t)
            self.entry_msg.delete(0, tk.END)

    def add_bubble(self, m):
        is_me = (int(m['sender_id']) == int(self.client.user_id))
        ChatBubble(self.msg_scroll, m['content'], is_me, m['timestamp']).pack(fill="x", pady=5)
        self.after(10, self.scroll_btm)

    def scroll_btm(self): self.msg_scroll._parent_canvas.yview_moveto(1.0)

    def process_queue(self):
        try:
            while not self.client.message_queue.empty():
                t, d = self.client.message_queue.get_nowait()
                if t == 'new_message':
                    if self.current_pid and (d['sender_id'] == self.current_pid or d['receiver_id'] == self.current_pid):
                        self.add_bubble(d)
                elif t == 'new_request':
                    if self.mode == "friends": self.refresh_sidebar()
        except: pass
        self.after(100, self.process_queue)
    
    def on_close(self):
        self.client.close()
        self.destroy()

# --- Login / Register Window ---
class LoginApp(ctk.CTk):
    def __init__(self, client_logic):
        super().__init__()
        self.client = client_logic
        self.title("Messenger")
        self.geometry("400x700")
        self.configure(fg_color="white")
        
        self.avatar_base64 = None

        self.tab = ctk.CTkTabview(self, fg_color="white")
        self.tab.pack(fill="both", expand=True, padx=20, pady=20)
        self.tab.add("Login")
        self.tab.add("Sign Up")

        # LOGIN UI
        l = self.tab.tab("Login")
        ctk.CTkLabel(l, text="Welcome", font=("Arial", 24, "bold"), text_color="black").pack(pady=30)
        self.l_user = ctk.CTkEntry(l, placeholder_text="Username", height=45)
        self.l_user.pack(pady=10, fill="x")
        self.l_pass = ctk.CTkEntry(l, placeholder_text="Password", show="*", height=45)
        self.l_pass.pack(pady=10, fill="x")
        ctk.CTkButton(l, text="Log In", height=45, fg_color=COLOR_ACCENT, command=self.do_login).pack(pady=30, fill="x")

        # REGISTER UI
        r = self.tab.tab("Sign Up")
        r_scroll = ctk.CTkScrollableFrame(r, fg_color="transparent")
        r_scroll.pack(fill="both", expand=True)

        self.r_first = ctk.CTkEntry(r_scroll, placeholder_text="First Name", height=40)
        self.r_first.pack(pady=5, fill="x")
        self.r_last = ctk.CTkEntry(r_scroll, placeholder_text="Last Name", height=40)
        self.r_last.pack(pady=5, fill="x")
        self.r_user = ctk.CTkEntry(r_scroll, placeholder_text="Username (Login)", height=40)
        self.r_user.pack(pady=5, fill="x")
        self.r_email = ctk.CTkEntry(r_scroll, placeholder_text="Email", height=40)
        self.r_email.pack(pady=5, fill="x")
        self.r_pass = ctk.CTkEntry(r_scroll, placeholder_text="Password", show="*", height=40)
        self.r_pass.pack(pady=5, fill="x")
        self.r_dob = ctk.CTkEntry(r_scroll, placeholder_text="Birth Date (DD/MM/YYYY)", height=40)
        self.r_dob.pack(pady=5, fill="x")
        self.r_gender = ctk.CTkComboBox(r_scroll, values=["Male", "Female", "Other"], height=40)
        self.r_gender.pack(pady=5, fill="x")
        self.btn_avt = ctk.CTkButton(r_scroll, text="Upload Avatar", fg_color="gray", command=self.upload_avt)
        self.btn_avt.pack(pady=15, fill="x")
        self.lbl_avt = ctk.CTkLabel(r_scroll, text="", font=("Arial", 10))
        self.lbl_avt.pack()
        ctk.CTkButton(r_scroll, text="Create Account", height=45, fg_color=COLOR_ACCENT, command=self.do_reg).pack(pady=20, fill="x")

    def upload_avt(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png;*.jpg;*.jpeg")])
        if path:
            try:
                img = Image.open(path)
                img.thumbnail((150, 150))
                buff = io.BytesIO()
                img.save(buff, format="PNG")
                self.avatar_base64 = base64.b64encode(buff.getvalue()).decode('utf-8')
                self.lbl_avt.configure(text="Image Selected ✓", text_color="green")
            except: messagebox.showerror("Error", "Invalid Image")

    def do_login(self):
        ok, data = self.client.login(self.l_user.get(), self.l_pass.get())
        if ok:
            self.destroy()
        else: messagebox.showerror("Error", data)

    def do_reg(self):
        d_name = f"{self.r_first.get()} {self.r_last.get()}".strip()
        if not d_name: d_name = self.r_user.get()
        payload = {
            "username": self.r_user.get(), "password": self.r_pass.get(),
            "email": self.r_email.get(), "display_name": d_name,
            "dob": self.r_dob.get(), "gender": self.r_gender.get(),
            "avatar": self.avatar_base64
        }
        ok, data = self.client.register(payload)
        if ok: messagebox.showinfo("Success", "Registered! Please Login.")
        else: messagebox.showerror("Error", data.get('error'))

if __name__ == "__main__":
    client = ChatClient()
    app = LoginApp(client)
    app.mainloop()
    
    if client.token:
        client.connect_websocket()
        ChatApp(client).mainloop()