import streamlit as st
from supabase import create_client, Client
import pandas as pd
import time

# --- 页面配置 ---
st.set_page_config(page_title="🀄 棋牌实时同步计分系统", layout="centered")

# --- 1. 初始化 Supabase 连接 ---
@st.cache_resource
def init_connection() -> Client:
    # 确保你已经在 Streamlit Cloud 的 Secrets 中配置了这两个 Key
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

st.title("🀄 棋牌实时同步计分系统")

# --- 2. 房间登录系统 ---
if "room_id" not in st.session_state:
    st.subheader("🔑 进入房间")
    room_input = st.text_input("请输入房间号 (如：8888)", placeholder="相同房间号数据互通")
    user_name = st.text_input("你的名字", placeholder="例如：张三")
    
    if st.button("进入房间", type="primary"):
        if room_input and user_name:
            st.session_state.room_id = room_input
            st.session_state.my_name = user_name
            st.rerun()
        else:
            st.error("请填入房间号和名字")
    st.stop()

# --- 3. 获取云端数据 ---
room_id = st.session_state.room_id

def get_room_data():
    try:
        response = supabase.table("game_rounds").select("*").eq("room_id", room_id).order("round_number").execute()
        return response.data
    except Exception as e:
        st.error(f"数据库连接失败: {e}")
        return []

raw_data = get_room_data()

st.sidebar.info(f"🏠 房间：**{room_id}** \n👤 身份：**{st.session_state.my_name}**")
if st.sidebar.button("🔄 刷新全员比分"):
    st.rerun()

# --- 4. 数据解析 ---
if not raw_data:
    st.warning("本房间暂无数据。")
    st.subheader("⚙️ 初始化新房间")
    names_str = st.text_area("输入所有玩家名字（用逗号或空格隔开）", placeholder="张三, 李四, 王五, 赵六")
    
    if st.button("创建房间"):
        names = [n.strip() for n in names_str.replace("，", ",").replace(" ", ",").split(",") if n.strip()]
        if len(names) >= 3:
            init_details = {name: 0.0 for name in names}
            init_details["茶水费"] = 0.0
            init_details["操作人"] = "系统初始化"
            supabase.table("game_rounds").insert({"room_id": room_id, "round_number": 0, "details": init_details}).execute()
            st.success("创建成功！")
            time.sleep(1)
            st.rerun()
        else:
            st.error("至少需要 3 名玩家")
    st.stop()

# 解析历史数据
history_list = []
players_set = set()
for row in raw_data:
    detail = row["details"]
    record = {"局数": row["round_number"]}
    for k, v in detail.items():
        record[k] = v
        if k not in ["茶水费", "操作人"]: players_set.add(k)
    history_list.append(record)

df_history = pd.DataFrame(history_list)
players = sorted(list(players_set))
current_round_num = max([row["round_number"] for row in raw_data])

# --- 5. 实时战况看板 ---
st.header("📊 实时战况")
current_scores = {p: df_history[p].sum() for p in players}
tea_pool = df_history["茶水费"].sum() if "茶水费" in df_history.columns else 0.0

cols = st.columns(len(players) + 1)
for i, p in enumerate(players):
    cols[i].metric(p, round(current_scores[p], 2))
cols[-1].metric("☕ 茶水池", round(tea_pool, 2))

st.divider()

# --- 6. 快捷记账区域 ---
st.header("📝 提交分数")

# 初始化临时分数缓存
if "temp_scores" not in st.session_state:
    st.session_state.temp_scores = {p: 0.0 for p in players}

def add_score(player, amount):
    st.session_state.temp_scores[player] += amount

st.write(f"正在录入第 **{current_round_num + 1}** 局")

for p in players:
    with st.container():
        c1, c2 = st.columns([1, 2])
        c1.write(f"**{p}**")
        # 绑定到 session_state
        st.session_state.temp_scores[p] = c2.number_input(
            f"分值_{p}", value=st.session_state.temp_scores[p], step=1.0, key=f"in_{p}", label_visibility="collapsed"
        )
        
        # 四个快捷按钮
        b1, b2, b3, b4 = st.columns(4)
        if b1.button("-10", key=f"m10_{p}"): add_score(p, -10); st.rerun()
        if b2.button("-5", key=f"m5_{p}"): add_score(p, -5); st.rerun()
        if b3.button("+5", key=f"p5_{p}"): add_score(p, 5); st.rerun()
        if b4.button("+10", key=f"p10_{p}"): add_score(p, 10); st.rerun()
    st.write("")

# 茶水费和提交
t_col, s_col = st.columns([1, 1])
tea_val = t_col.number_input("本局抽水 (茶水费)", value=0.0, step=5.0)

if s_col.button("✅ 提交并同步全员", type="primary", use_container_width=True):
    total = sum(st.session_state.temp_scores.values())
    if round(total, 2) != 0:
        st.error(f"分数不平！当前总和：{total}")
    else:
        details = {p: s for p, s in st.session_state.temp_scores.items()}
        details["茶水费"] = tea_val
        details["操作人"] = st.session_state.my_name
        supabase.table("game_rounds").insert({"room_id": room_id, "round_number": current_round_num + 1, "details": details}).execute()
        # 重置并刷新
        for p in players: st.session_state.temp_scores[p] = 0.0
        st.success("同步成功！")
        time.sleep(0.5)
        st.rerun()

if st.button("🧹 重置本局输入", use_container_width=True):
    for p in players: st.session_state.temp_scores[p] = 0.0
    st.rerun()

st.divider()

# --- 7. 历史明细 ---
st.header("📜 历史流水")
display_df = df_history[df_history["局数"] > 0]
if not display_df.empty:
    cols_order = ["局数"] + players + ["茶水费", "操作人"]
    st.dataframe(display_df[cols_order].fillna(0), use_container_width=True, hide_index=True)
