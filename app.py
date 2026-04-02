import streamlit as st
from supabase import create_client, Client
import pandas as pd
import time

# --- 页面配置 ---
st.set_page_config(page_title="🀄 棋牌同步计分系统", layout="wide") # 改为宽屏模式方便查看长表格

# --- 1. 初始化 Supabase 连接 ---
@st.cache_resource
def init_connection() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

st.title("🀄 棋牌实时同步计分系统")

# --- 2. 房间登录系统 ---
if "room_id" not in st.session_state:
    st.subheader("🔑 进入房间")
    room_input = st.text_input("请输入房间号", placeholder="如：8888")
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

# --- 4. 数据解析与累计分数计算 ---
if not raw_data:
    st.warning("本房间暂无数据。")
    st.subheader("⚙️ 初始化新房间")
    names_str = st.text_area("输入玩家名字（用逗号或空格隔开）", placeholder="张三, 李四, 王五")
    
    if st.button("创建房间"):
        names = [n.strip() for n in names_str.replace("，", ",").replace(" ", ",").split(",") if n.strip()]
        if len(names) >= 2:
            init_details = {name: 0.0 for name in names}
            init_details["茶水费"] = 0.0
            init_details["操作人"] = "系统初始化"
            supabase.table("game_rounds").insert({"room_id": room_id, "round_number": 0, "details": init_details}).execute()
            st.success("创建成功！")
            time.sleep(1)
            st.rerun()
        else:
            st.error("至少需要 2 名玩家")
    st.stop()

# 解析基础数据
history_list = []
players_set = set()
for row in raw_data:
    detail = row["details"]
    record = {"id": row["id"], "局数": row["round_number"]}
    for k, v in detail.items():
        record[k] = v
        if k not in ["茶水费", "操作人"]: players_set.add(k)
    history_list.append(record)

df_history = pd.DataFrame(history_list)
players = sorted(list(players_set))
current_round_num = max([row["round_number"] for row in raw_data])

# --- 核心修改：计算累计分数 ---
# 对每一位玩家计算从第一局到当前的累加和
for p in players:
    df_history[f"{p}(累计)"] = df_history[p].cumsum()

# --- 5. 实时战况看板 ---
st.header("📊 实时战况")
current_scores = {p: df_history[p].sum() for p in players}
tea_pool = df_history["茶水费"].sum() if "茶水费" in df_history.columns else 0.0

cols = st.columns(len(players) + 1)
for i, p in enumerate(players):
    cols[i].metric(p, round(current_scores[p], 2))
cols[-1].metric("☕ 茶水池合计", round(tea_pool, 2))

st.divider()

# --- 6. 记账区域 ---
st.header("📝 提交分数")
score_options = [0, 5, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100, -5, -10, -15, -20, -25, -30, -40, -50, -60, -80, -100]
score_options = sorted(list(set(score_options)), reverse=True)

current_round_input = {}
cols_input = st.columns(len(players)) 
for i, p in enumerate(players):
    with cols_input[i]:
        current_round_input[p] = st.selectbox(f"**{p}**", score_options, index=score_options.index(0), key=f"sb_{p}")

tea_val = st.number_input("本局扣除茶水费 (如有)", value=0.0, step=5.0)

if st.button("✅ 确认提交本局", type="primary", use_container_width=True):
    total = sum(current_round_input.values())
    if round(total, 2) != 0:
        st.error(f"⚠️ 分数不平！当前所有人合计：{total} (必须为0)")
    else:
        details = {p: s for p, s in current_round_input.items()}
        details["茶水费"] = tea_val
        details["操作人"] = st.session_state.my_name
        supabase.table("game_rounds").insert({"room_id": room_id, "round_number": current_round_num + 1, "details": details}).execute()
        st.success("记账成功！")
        time.sleep(0.5)
        st.rerun()

st.divider()

# --- 7. 历史流水与管理 (包含累计分数) ---
st.header("📜 历史流水 (含每局累计)")

# 过滤掉初始化的第 0 局
display_df = df_history[df_history["局_num" if "局_num" in df_history.columns else "局数"] > 0].copy()

if not display_df.empty:
    # 构造显示的列顺序：局数 -> [玩家A, 玩家A累计, 玩家B, 玩家B累计...] -> 茶水费 -> 操作人
    dynamic_cols = []
    for p in players:
        dynamic_cols.append(p)
        dynamic_cols.append(f"{p}(累计)")
    
    final_cols = ["局数"] + dynamic_cols + ["茶水费", "操作人"]
    
    # 倒序排列，让最新的在最上面
    reversed_df = display_df.iloc[::-1]
    
    # 使用 st.dataframe 展示，并对累计分数进行高亮或样式处理
    st.dataframe(
        reversed_df[final_cols].style.format(precision=1),
        use_container_width=True, 
        hide_index=True
    )

    # --- 删除功能区 ---
    st.subheader("⚠️ 数据修正")
    with st.expander("点击展开管理选项（删除错误记录）"):
        target_round = st.selectbox("选择要删除的局数", options=display_df["局数"].tolist())
        target_id = display_df[display_df["局数"] == target_round]["id"].values[0]
        
        if st.button(f"🔥 确认永久删除第 {target_round} 局", type="secondary", use_container_width=True):
            supabase.table("game_rounds").delete().eq("id", int(target_id)).execute()
            st.warning(f"第 {target_round} 局已从数据库删除！")
            time.sleep(1)
            st.rerun()
else:
    st.info("暂无打牌记录")
