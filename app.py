import streamlit as st
import sqlite3
from datetime import date, datetime
from pathlib import Path
import pandas as pd

DB_PATH = Path(__file__).parent / "smart_money.db"

CATEGORIES = [
    "Food", "Shopping", "Travel", "Bills", "Entertainment",
    "Groceries", "Health", "Education", "Rent", "Salary", "Other"
]
PAYMENT_METHODS = ["UPI", "Cash", "Debit Card", "Credit Card", "Bank Transfer", "Other"]

KEYWORDS = {
    "Food": ["swiggy", "zomato", "restaurant", "hotel", "cafe", "tea", "coffee", "food"],
    "Shopping": ["amazon", "flipkart", "myntra", "meesho", "shopping", "ajio"],
    "Travel": ["uber", "ola", "metro", "bus", "fuel", "petrol", "rapido", "travel"],
    "Bills": ["electricity", "eb", "airtel", "jio", "vi", "internet", "wifi", "recharge", "bill"],
    "Entertainment": ["netflix", "prime", "hotstar", "spotify", "movie", "cinema", "game"],
    "Groceries": ["grocery", "vegetables", "milk", "supermarket", "dmart", "provision"],
    "Health": ["hospital", "doctor", "pharmacy", "medicine", "medical"],
    "Education": ["school", "college", "course", "book", "education"],
    "Rent": ["rent", "house rent", "room rent"],
    "Salary": ["salary", "payroll", "income"],
}

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('Income','Expense')),
            category TEXT NOT NULL,
            description TEXT,
            payment_method TEXT,
            transaction_date TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            UNIQUE(month, category)
        )
    """)
    conn.commit()
    conn.close()

def add_transaction(amount, tx_type, category, description, payment_method, tx_date):
    conn = get_conn()
    conn.execute("""
        INSERT INTO transactions
        (amount, type, category, description, payment_method, transaction_date, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        amount, tx_type, category, description, payment_method,
        tx_date.isoformat(), datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()

def get_transactions():
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM transactions ORDER BY transaction_date DESC, id DESC", conn
    )
    conn.close()
    return df

def delete_transaction(tx_id):
    conn = get_conn()
    conn.execute("DELETE FROM transactions WHERE id = ?", (int(tx_id),))
    conn.commit()
    conn.close()

def save_budget(month, category, amount):
    conn = get_conn()
    conn.execute("""
        INSERT INTO budgets(month, category, amount)
        VALUES (?, ?, ?)
        ON CONFLICT(month, category)
        DO UPDATE SET amount = excluded.amount
    """, (month, category, amount))
    conn.commit()
    conn.close()

def get_budgets(month):
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT category, amount FROM budgets WHERE month = ? ORDER BY category",
        conn, params=(month,)
    )
    conn.close()
    return df

def suggest_category(text):
    text = (text or "").lower()
    for category, words in KEYWORDS.items():
        if any(word in text for word in words):
            return category
    return "Other"

def money(value):
    return f"₹{value:,.0f}"

def month_df(df, month):
    if df.empty:
        return df.copy()
    return df[df["transaction_date"].str.startswith(month)].copy()

def generate_insights(df, month, budgets):
    mdf = month_df(df, month)
    if mdf.empty:
        return ["Add a few expenses and I'll analyze your spending."]

    expenses = mdf[mdf["type"] == "Expense"].copy()
    income = mdf[mdf["type"] == "Income"]["amount"].sum()

    if expenses.empty:
        return ["You have no recorded expenses for this month yet."]

    total = expenses["amount"].sum()
    by_cat = expenses.groupby("category")["amount"].sum().sort_values(ascending=False)
    insights = []

    top_cat = by_cat.index[0]
    top_amount = by_cat.iloc[0]
    insights.append(
        f"Your biggest expense category is {top_cat}: {money(top_amount)} "
        f"({top_amount / total:.0%} of recorded spending)."
    )

    if income > 0:
        savings = income - total
        if savings >= 0:
            insights.append(f"You have {money(savings)} left from recorded income this month.")
        else:
            insights.append(f"You have spent {money(abs(savings))} more than your recorded income.")

    if not budgets.empty:
        for _, row in budgets.iterrows():
            cat = row["category"]
            budget = float(row["amount"])
            spent = float(by_cat.get(cat, 0))
            if budget > 0 and spent >= budget:
                insights.append(
                    f"⚠️ {cat} is over budget by {money(spent - budget)}."
                )
            elif budget > 0 and spent >= budget * 0.8:
                insights.append(
                    f"⚠️ {cat} has used {spent / budget:.0%} of its budget."
                )

    # A simple, transparent "AI-style" observation for MVP.
    if len(expenses) >= 5:
        avg = expenses["amount"].mean()
        insights.append(
            f"You recorded {len(expenses)} expenses this month, averaging {money(avg)} per expense."
        )

    return insights[:5]

st.set_page_config(
    page_title="Smart Money",
    page_icon="💰",
    layout="wide"
)

init_db()

st.markdown("""
<style>
.block-container {padding-top: 2rem; padding-bottom: 3rem;}
.big-number {font-size: 2rem; font-weight: 700;}
.small-muted {color: #777;}
.card {
    padding: 1rem;
    border: 1px solid #ddd;
    border-radius: 12px;
    margin-bottom: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

st.title("💰 Smart Money")
st.caption("A simple personal money manager for India — MVP")

df = get_transactions()

# Sidebar navigation
page = st.sidebar.radio(
    "Navigate",
    ["🏠 Dashboard", "➕ Add Transaction", "📋 Transactions", "🎯 Budgets", "🤖 Analyze My Spending"],
)

today = date.today()
selected_month = st.sidebar.date_input(
    "Month",
    value=today.replace(day=1),
).strftime("%Y-%m")

if page == "➕ Add Transaction":
    st.header("Add Transaction")

    tx_type = st.radio("Type", ["Expense", "Income"], horizontal=True)

    with st.form("transaction_form"):
        amount = st.number_input("Amount (₹)", min_value=0.0, step=50.0, format="%.2f")
        description = st.text_input(
            "Description",
            placeholder="e.g. Swiggy lunch, Uber, salary..."
        )

        suggested = suggest_category(description)

        category_options = CATEGORIES
        default_index = category_options.index(suggested) if suggested in category_options else 0
        category = st.selectbox("Category", category_options, index=default_index)

        payment = st.selectbox("Payment method", PAYMENT_METHODS)
        tx_date = st.date_input("Date", value=today)

        submitted = st.form_submit_button("SAVE TRANSACTION", use_container_width=True)

        if submitted:
            if amount <= 0:
                st.error("Please enter an amount greater than ₹0.")
            else:
                add_transaction(
                    amount, tx_type, category, description, payment, tx_date
                )
                st.success(f"{tx_type} of {money(amount)} saved.")
                st.rerun()

elif page == "📋 Transactions":
    st.header("Transactions")

    if df.empty:
        st.info("No transactions yet. Add your first transaction.")
    else:
        search = st.text_input("Search", placeholder="Search description, category, payment method...")
        filtered = df.copy()

        if search:
            mask = (
                filtered["description"].fillna("").str.contains(search, case=False, na=False)
                | filtered["category"].str.contains(search, case=False, na=False)
                | filtered["payment_method"].fillna("").str.contains(search, case=False, na=False)
            )
            filtered = filtered[mask]

        display = filtered[[
            "id", "transaction_date", "type", "category",
            "description", "payment_method", "amount"
        ]].copy()

        display["amount"] = display["amount"].map(money)
        display = display.rename(columns={
            "id": "ID",
            "transaction_date": "Date",
            "type": "Type",
            "category": "Category",
            "description": "Description",
            "payment_method": "Payment",
            "amount": "Amount",
        })

        st.dataframe(display, use_container_width=True, hide_index=True)

        if not filtered.empty:
            st.divider()
            st.subheader("Delete a transaction")
            tx_id = st.number_input(
                "Transaction ID",
                min_value=1,
                step=1,
                value=int(filtered.iloc[0]["id"])
            )
            if st.button("Delete selected transaction"):
                delete_transaction(tx_id)
                st.success("Transaction deleted.")
                st.rerun()

elif page == "🎯 Budgets":
    st.header("Monthly Budgets")
    st.caption(f"Budget month: {selected_month}")

    with st.form("budget_form"):
        category = st.selectbox(
            "Category",
            [c for c in CATEGORIES if c != "Salary"]
        )
        amount = st.number_input("Budget amount (₹)", min_value=0.0, step=100.0)
        save = st.form_submit_button("SAVE BUDGET", use_container_width=True)

        if save:
            if amount <= 0:
                st.error("Budget must be greater than ₹0.")
            else:
                save_budget(selected_month, category, amount)
                st.success(f"{category} budget saved.")
                st.rerun()

    budgets = get_budgets(selected_month)
    mdf = month_df(df, selected_month)
    expenses = mdf[mdf["type"] == "Expense"] if not mdf.empty else pd.DataFrame()

    st.subheader("Current budgets")

    if budgets.empty:
        st.info("No budgets set for this month.")
    else:
        for _, row in budgets.iterrows():
            cat = row["category"]
            budget = float(row["amount"])
            spent = 0.0
            if not expenses.empty:
                spent = float(expenses.loc[expenses["category"] == cat, "amount"].sum())

            ratio = min(spent / budget, 1.0) if budget else 0
            st.write(f"**{cat}** — {money(spent)} / {money(budget)}")
            st.progress(ratio)

            if spent > budget:
                st.error(f"Over budget by {money(spent - budget)}")
            elif spent >= budget * 0.8:
                st.warning(f"{budget - spent:,.0f} remaining")
            else:
                st.success(f"{budget - spent:,.0f} remaining")

elif page == "🤖 Analyze My Spending":
    st.header("🤖 Analyze My Spending")
    st.caption(f"Analysis for {selected_month}")

    budgets = get_budgets(selected_month)
    insights = generate_insights(df, selected_month, budgets)

    st.subheader("Your money report")
    for insight in insights:
        st.write("• " + insight)

    mdf = month_df(df, selected_month)
    expenses = mdf[mdf["type"] == "Expense"] if not mdf.empty else pd.DataFrame()

    if not expenses.empty:
        st.subheader("Category breakdown")
        chart = expenses.groupby("category")["amount"].sum().sort_values(ascending=False)
        st.bar_chart(chart)

        st.subheader("Top expenses")
        top = expenses.sort_values("amount", ascending=False).head(5)
        for _, row in top.iterrows():
            st.write(
                f"**{money(row['amount'])}** — {row['category']} — "
                f"{row['description'] or 'No description'}"
            )

    st.info(
        "MVP note: these insights are generated from your recorded transaction data. "
        "They are not professional financial advice."
    )

else:
    st.header("Dashboard")
    st.caption(f"Overview for {selected_month}")

    mdf = month_df(df, selected_month)

    income = float(mdf.loc[mdf["type"] == "Income", "amount"].sum()) if not mdf.empty else 0
    expenses = float(mdf.loc[mdf["type"] == "Expense", "amount"].sum()) if not mdf.empty else 0
    remaining = income - expenses

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Monthly Income", money(income))
    with c2:
        st.metric("Spent", money(expenses))
    with c3:
        st.metric("Remaining", money(remaining))

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("Spending by category")
        if mdf.empty or mdf[mdf["type"] == "Expense"].empty:
            st.info("No expenses recorded this month.")
        else:
            by_cat = (
                mdf[mdf["type"] == "Expense"]
                .groupby("category")["amount"]
                .sum()
                .sort_values(ascending=False)
            )
            st.bar_chart(by_cat)

    with right:
        st.subheader("Recent transactions")
        if df.empty:
            st.info("No transactions yet.")
        else:
            recent = df.head(8)
            for _, row in recent.iterrows():
                sign = "+" if row["type"] == "Income" else "-"
                st.write(
                    f"**{sign}{money(row['amount'])}**  "
                    f"{row['category']}  ·  {row['description'] or ''}"
                )

    st.divider()
    st.subheader("Quick insight")

    if expenses > 0:
        mcat = (
            mdf[mdf["type"] == "Expense"]
            .groupby("category")["amount"]
            .sum()
            .sort_values(ascending=False)
        )
        top_cat = mcat.index[0]
        st.write(
            f"Your largest spending category this month is **{top_cat}** "
            f"at **{money(mcat.iloc[0])}**."
        )
    else:
        st.write("Start adding expenses to see personalized insights.")
