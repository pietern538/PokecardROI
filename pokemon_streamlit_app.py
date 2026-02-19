import sqlite3
import pandas as pd
import streamlit as st
from PIL import Image
import requests
from io import BytesIO

DB_PATH = "pokemon_cards.db"

st.set_page_config(page_title="Pokémon Card ROI Explorer", layout="wide")
st.title("Pokémon Card ROI Explorer")


# Connect to DB and fetch sets
@st.cache_data(show_spinner=False)
def get_sets():
    conn = sqlite3.connect(DB_PATH)
    sets = pd.read_sql_query("SELECT DISTINCT set_slug, set_name FROM cards ORDER BY set_name", conn)
    conn.close()
    return sets

@st.cache_data(show_spinner=False)
def get_all_cards():
    conn = sqlite3.connect(DB_PATH)
    query = '''
        SELECT cards.set_slug, cards.set_name, cards.id, cards.name, cards.card_number, cards.variant, cards.rarity, cards.image, prices.avg as near_mint_avg, psa9.avg as psa9_avg, psa10.avg as psa10_avg, prices.sale_count
        FROM cards
        LEFT JOIN prices ON cards.id = prices.card_id AND prices.grade = 'NEAR_MINT' AND prices.source = 'cardmarket_unsold'
        LEFT JOIN prices AS psa9 ON cards.id = psa9.card_id AND psa9.grade = 'PSA_9' AND psa9.source = 'cardmarket_unsold'
        LEFT JOIN prices AS psa10 ON cards.id = psa10.card_id AND psa10.grade = 'PSA_10' AND psa10.source = 'cardmarket_unsold'
        GROUP BY cards.id
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    grading_cost = 20
    df["psa10_roi"] = ((df["psa10_avg"] - (df["near_mint_avg"] + grading_cost)) / (df["near_mint_avg"] + grading_cost)) * 100
    return df

@st.cache_data(show_spinner=False)
def get_cards_by_set(set_slug):
    conn = sqlite3.connect(DB_PATH)
    query = '''
        SELECT cards.id, cards.name, cards.card_number, cards.variant, cards.rarity, cards.image, prices.avg as near_mint_avg, psa9.avg as psa9_avg, psa10.avg as psa10_avg, prices.sale_count
        FROM cards
        LEFT JOIN prices ON cards.id = prices.card_id AND prices.grade = 'NEAR_MINT' AND prices.source = 'cardmarket_unsold'
        LEFT JOIN prices AS psa9 ON cards.id = psa9.card_id AND psa9.grade = 'PSA_9' AND psa9.source = 'cardmarket_unsold'
        LEFT JOIN prices AS psa10 ON cards.id = psa10.card_id AND psa10.grade = 'PSA_10' AND psa10.source = 'cardmarket_unsold'
        WHERE cards.set_slug = ?
        GROUP BY cards.id
    '''
    df = pd.read_sql_query(query, conn, params=(set_slug,))
    conn.close()
    grading_cost = 20
    df["psa10_roi"] = ((df["psa10_avg"] - (df["near_mint_avg"] + grading_cost)) / (df["near_mint_avg"] + grading_cost)) * 100
    return df

def show_card(card, modal_key=None):
    import streamlit as st
    import urllib.parse
    # Card cell: image (smaller) and info stacked vertically
    if pd.notnull(card["image"]):
        try:
            response = requests.get(card["image"], timeout=5)
            img = Image.open(BytesIO(response.content))
            st.image(img, width=120)
            # Open details in a new page
            import streamlit as st
            import urllib.parse
            card_url = f"/" + "?page=Card+Details&card_id={}".format(card['id'])
            st.markdown(
                f'<a href="{card_url}" target="_blank"><button>🔍 View details</button></a>',
                unsafe_allow_html=True
            )
        except Exception:
            st.write("[Image not available]")
    else:
        st.write("[No image]")
    card_number = card['card_number'] if 'card_number' in card and pd.notnull(card['card_number']) else ''
    st.markdown(f"**{card['name']} #{card_number}**" if card_number else f"**{card['name']}**")
    st.write(f"Raw Price: €{card['near_mint_avg']:.2f}" if pd.notnull(card['near_mint_avg']) else "Raw Price: N/A")
    # Calculate ROI if missing
    grading_cost = 20
    psa10_roi = card['psa10_roi'] if 'psa10_roi' in card else None
    if psa10_roi is None and pd.notnull(card.get('psa10_avg')) and pd.notnull(card.get('near_mint_avg')):
        try:
            psa10_roi = ((card['psa10_avg'] - (card['near_mint_avg'] + grading_cost)) / (card['near_mint_avg'] + grading_cost)) * 100
        except Exception:
            psa10_roi = None
    st.write(f"ROI: {psa10_roi:.1f}%" if psa10_roi is not None and pd.notnull(psa10_roi) else "ROI: N/A")

# Navigation

import urllib.parse


# Query params for navigation (Streamlit 1.30+)
query_params = st.query_params

def set_page_and_set_slug(page_name, set_slug=None):
    params = {"page": page_name}
    if set_slug:
        params["set_slug"] = set_slug
    st.query_params.update(params)


page = query_params.get("page") if "page" in query_params else None
pages = ["Card Browser", "Sets by ROI", "Pokémon Investment List", "Card Details"]
# Top navigation (hide on Card Details page)
if page != "Card Details":
    nav_pages = [p for p in pages if p != "Card Details"]
    nav_cols = st.columns(len(nav_pages))
    nav_clicked = None
    for idx, nav_page in enumerate(nav_pages):
        if nav_cols[idx].button(nav_page, key=f"navbtn_{nav_page}"):
            nav_clicked = nav_page
    if nav_clicked and nav_clicked != page:
        new_params = dict(st.query_params)
        new_params["page"] = nav_clicked
        if "pokemon" in new_params:
            del new_params["pokemon"]
        st.query_params.clear()
        st.query_params.update(new_params)
        st.rerun()
    if not page:
        page = nav_pages[0]
    else:
        if isinstance(page, list):
            page = page[0]
else:
    # If page is a list (from query_params), get the first value
    if isinstance(page, list):
        page = page[0]

# Main page navigation
if page == "Card Details":
    card_id = query_params.get("card_id")
    if card_id:
        if isinstance(card_id, list):
            card_id = card_id[0]
        # Find card in all cards (ID may be string, do not cast to int)
        all_cards = get_all_cards()
        card = all_cards[all_cards["id"] == card_id]
        if not card.empty:
            card = card.iloc[0]
            st.header(f"Details for {card['name']} #{card['card_number']}")
            if pd.notnull(card["image"]):
                try:
                    response = requests.get(card["image"], timeout=5)
                    img = Image.open(BytesIO(response.content))
                    st.image(img, width=350)
                except Exception:
                    st.write("[Image not available]")
            st.markdown(f"**{card['name']} #{card['card_number']}**")
            st.write(f"Variant: {card['variant']} | Rarity: {card['rarity']}")
            st.write(f"Near Mint Avg: €{card['near_mint_avg']:.2f}" if pd.notnull(card['near_mint_avg']) else "Near Mint Avg: N/A")
            st.write(f"PSA 9 Avg: €{card['psa9_avg']:.2f}" if pd.notnull(card['psa9_avg']) else "PSA 9 Avg: N/A")
            st.write(f"PSA 10 Avg: €{card['psa10_avg']:.2f}" if pd.notnull(card['psa10_avg']) else "PSA 10 Avg: N/A")
            # Calculate ROI if missing
            grading_cost = 20
            psa10_roi = card['psa10_roi'] if 'psa10_roi' in card else None
            if psa10_roi is None and pd.notnull(card.get('psa10_avg')) and pd.notnull(card.get('near_mint_avg')):
                try:
                    psa10_roi = ((card['psa10_avg'] - (card['near_mint_avg'] + grading_cost)) / (card['near_mint_avg'] + grading_cost)) * 100
                except Exception:
                    psa10_roi = None
            st.write(f"PSA 10 ROI: {psa10_roi:.1f}%" if psa10_roi is not None and pd.notnull(psa10_roi) else "PSA 10 ROI: N/A")
            st.write(f"Sales Count: {int(card['sale_count']) if pd.notnull(card['sale_count']) else 'N/A'}")
            if st.button("⬅ Back", key="back_card_details"):
                st.query_params.clear()
                st.query_params.update({"page": "Card Browser"})
                st.rerun()
        else:
            st.error("Card not found.")
    else:
        st.error("No card ID provided.")
elif page == "Card Browser":
    search_query = st.text_input("Search card name (leave empty to show all)", "", key="card_search")
    sets = get_sets()
    set_names = ["All Sets"] + sets["set_name"].tolist()
    set_slugs = [None] + sets["set_slug"].tolist()
    set_slug_param = query_params.get("set_slug") if "set_slug" in query_params else None
    pokemon_param = query_params.get("pokemon") if "pokemon" in query_params else None
    if pokemon_param:
        if isinstance(pokemon_param, list):
            pokemon_param = pokemon_param[0]
        # Show all cards for this Pokémon across all sets
        all_cards = get_all_cards()
        # Ensure ROI column exists and fill NaN with very low value for sorting
        if "psa10_roi" not in all_cards.columns:
            grading_cost = 20
            all_cards["psa10_roi"] = ((all_cards["psa10_avg"] - (all_cards["near_mint_avg"] + grading_cost)) / (all_cards["near_mint_avg"] + grading_cost)) * 100
        all_cards["psa10_roi"] = all_cards["psa10_roi"].fillna(-9999)
        cards = all_cards[all_cards["name"].str.startswith(pokemon_param)]
        # Apply search filter if present
        if search_query:
            cards = cards[cards["name"].str.contains(search_query, case=False, na=False)]
        # Sort by ROI descending, then by name
        cards = cards.sort_values(["psa10_roi", "name"], ascending=[False, True])
        st.write(f"### Cards for Pokémon: {pokemon_param} ({len(cards)}) (sorted by PSA 10 ROI)")
        # Back button to return to Pokémon Investment List
        if st.button("⬅ Back to Pokémon Investment List"):
            st.query_params.update({"page": "Pokémon Investment List"})
    else:
        # If set_slug is in query params, preselect it
        if set_slug_param:
            if isinstance(set_slug_param, list):
                set_slug_param = set_slug_param[0]
            # If set_slug_param is None or empty string, treat as All Sets
            if not set_slug_param or set_slug_param == "None":
                default_idx = 0
            elif set_slug_param in set_slugs:
                default_idx = set_slugs.index(set_slug_param)
            else:
                default_idx = 0
        else:
            default_idx = 0
        selected_set = st.selectbox("Select a set", set_names, index=default_idx, key="set_select")
        # If user changes the set, update query params
        if set_slug_param != set_slugs[set_names.index(selected_set)]:
            new_params = dict(st.query_params)
            if selected_set == "All Sets":
                if "set_slug" in new_params:
                    del new_params["set_slug"]
            else:
                new_params["set_slug"] = set_slugs[set_names.index(selected_set)]
            st.query_params.clear()
            st.query_params.update(new_params)
            st.rerun()
        if selected_set == "All Sets":
            cards = get_all_cards()
        else:
            set_slug = sets[sets["set_name"] == selected_set]["set_slug"].values[0]
            cards = get_cards_by_set(set_slug)
        # Apply search filter if present
        if search_query:
            cards = cards[cards["name"].str.contains(search_query, case=False, na=False)]
        cards["psa10_roi"] = cards["psa10_roi"].fillna(-9999)
        cards = cards.sort_values(["psa10_roi", "name"], ascending=[False, True], na_position="last").reset_index(drop=True)
        if selected_set == "All Sets":
            st.write(f"### All Cards ({len(cards)}) (sorted by PSA 10 ROI)")
        else:
            st.write(f"### Cards in {selected_set} ({len(cards)}) (sorted by PSA 10 ROI)")
    # Pagination for card grid
    cards_per_page = 24
    total_cards = len(cards)
    total_pages = max(1, (total_cards - 1) // cards_per_page + 1)
    page_num = st.number_input('Page', min_value=1, max_value=total_pages, value=1, step=1, key='card_page')
    start_idx = (page_num - 1) * cards_per_page
    end_idx = start_idx + cards_per_page
    paged_cards = cards.iloc[start_idx:end_idx]
    # Display cards in a 4-column grid
    cols = st.columns(4)
    for idx, card in paged_cards.iterrows():
        with cols[idx % 4]:
            show_card(card, modal_key=f"{page}_{idx}")
        if (idx + 1) % 4 == 0:
            st.write("")  # Add a row break
    st.write(f"Page {page_num} of {total_pages} ({total_cards} cards)")

elif page == "Sets by ROI":
    st.header("Sets Ranked by Average PSA 10 ROI")
    all_cards = get_all_cards()
    # Only consider cards with valid ROI
    roi_by_set = all_cards.dropna(subset=["psa10_roi"]).groupby(["set_slug", "set_name"]).agg(
        avg_psa10_roi=("psa10_roi", "mean"),
        num_cards=("id", "count")
    ).reset_index()
    roi_by_set = roi_by_set.sort_values("avg_psa10_roi", ascending=False)
    # Add clickable links to set names
    def make_set_link(row):
        url = f"?page=Card+Browser&set_slug={urllib.parse.quote(row['set_slug'])}"
        return f"[**{row['set_name']}**]({url})"
    roi_by_set["Set"] = roi_by_set.apply(make_set_link, axis=1)
    # Total sales per set
    sales_by_set = all_cards.groupby(["set_slug", "set_name"]).agg(
        total_sales=("sale_count", "sum")
    ).reset_index()
    sales_by_set = sales_by_set.sort_values("total_sales", ascending=False)
    sales_by_set["Set"] = sales_by_set.apply(make_set_link, axis=1)
    st.write("Click a set name to view its cards.")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Sets by ROI")
        st.write(
            roi_by_set[["Set", "avg_psa10_roi", "num_cards"]]
            .rename(columns={"avg_psa10_roi": "Avg PSA 10 ROI", "num_cards": "# Cards"})
            .to_markdown(index=False),
            unsafe_allow_html=True
        )
    with col2:
        st.markdown("#### Total Sales per Set")
        st.write(
            sales_by_set[["Set", "total_sales"]]
            .rename(columns={"total_sales": "Total Sales"})
            .to_markdown(index=False),
            unsafe_allow_html=True
        )

elif page == "Pokémon Investment List":
    poke_search = st.text_input("Search Pokémon name (leave empty to show all)", "", key="poke_search")
    st.header("Pokémon Investment List (by Sales & ROI)")
    all_cards = get_all_cards()
    # Extract Pokémon name (first word in card name)
    all_cards["pokemon"] = all_cards["name"].str.split().str[0]
    # Group by Pokémon, sum sales, average ROI, count cards
    agg = all_cards.groupby("pokemon").agg(
        total_sales=("sale_count", "sum"),
        avg_psa10_roi=("psa10_roi", "mean"),
        num_cards=("id", "count")
    ).reset_index()
    # Remove Pokémon with no sales or ROI
    agg = agg.dropna(subset=["avg_psa10_roi", "total_sales"])
    agg = agg[agg["total_sales"] > 0]
    # Sort by total sales and ROI
    agg = agg.sort_values(["avg_psa10_roi", "total_sales"], ascending=[False, False])
    # Filter by Pokémon search if present
    if poke_search:
        agg = agg[agg["pokemon"].str.contains(poke_search, case=False, na=False)]
    # Add clickable links to Pokémon names
    def make_pokemon_link(row):
        url = f"?page=Card+Browser&pokemon={urllib.parse.quote(row['pokemon'])}"
        return f"[**{row['pokemon']}**]({url})"
    agg["Pokémon"] = agg.apply(make_pokemon_link, axis=1)
    st.write("Click a Pokémon name to view all its cards.")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Investment Table")
        st.write(
            agg[["Pokémon", "num_cards", "total_sales", "avg_psa10_roi"]]
            .rename(columns={"num_cards": "# Cards", "total_sales": "Total Sales", "avg_psa10_roi": "Avg PSA 10 ROI"})
            .to_markdown(index=False),
            unsafe_allow_html=True
        )
    with col2:
        st.markdown("#### Total Sales per Pokémon")
        sales_sorted = agg[["Pokémon", "total_sales"]].rename(columns={"total_sales": "Total Sales"}).sort_values("Total Sales", ascending=False)
        st.write(
            sales_sorted.to_markdown(index=False),
            unsafe_allow_html=True
        )
