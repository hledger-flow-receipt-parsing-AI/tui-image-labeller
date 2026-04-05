from collections import Counter
from typing import Dict, List, Optional, Tuple

from hledger_core.TransactionObjects.Address import Address
from hledger_core.TransactionObjects.Receipt import Receipt
from hledger_core.TransactionObjects.ShopId import ShopId
from typeguard import typechecked


@typechecked
def get_relevant_shop_ids(
    *, labelled_receipts: List[Receipt], category_input: Optional[str] = None
) -> Dict[str, List[Tuple[int, ShopId]]]:
    """Load labelled_receipts and create a category-to-shop-id mapping with
    counts.

    Args:
        labelled_receipts: List of Receipt objects
        category_input: User-provided category to filter shop IDs

    Returns:
        Dict mapping categories to lists of (count, ShopId) tuples

    Raises:
        ValueError: If labelled_receipts list is empty
    """
    # if not labelled_receipts:
    #     raise ValueError("Receipts list cannot be empty")

    # Step 0: Create category-to-shop-id mapping with counts
    category_shop_counts: Dict[str, List[Tuple[int, ShopId]]] = {}

    # Extract category and shop ID pairs
    category_shop_pairs = [
        (r.receipt_category, r.shop_identifier)
        for r in labelled_receipts
        if r.receipt_category is not None and r.shop_identifier is not None
    ]

    # Group by category
    for category in {cat for cat, _ in category_shop_pairs}:
        # Get all shop IDs for this category
        shop_ids = [sid for cat, sid in category_shop_pairs if cat == category]
        # Convert ShopId to a hashable tuple for counting
        shop_id_tuples = [
            (
                sid["name"] if isinstance(sid, dict) else sid.name,
                (
                    Address(**sid["address"]).to_string()
                    if isinstance(sid, dict)
                    and isinstance(sid["address"], dict)
                    else sid.address.to_string()
                ),
                (
                    sid.get("shop_account_nr", "")
                    if isinstance(sid, dict)
                    else (sid.shop_account_nr or "")
                ),
            )
            for sid in shop_ids
        ]
        # Count occurrences of each shop ID
        shop_counts = Counter(shop_id_tuples)
        # Convert back to ShopId objects with counts, sorted by count descending
        category_shop_counts[category] = [
            (
                count,
                (
                    ShopId(
                        name=hashable_sid[0],
                        address=(
                            Address(**sid["address"])
                            if isinstance(sid, dict)
                            and isinstance(sid["address"], dict)
                            else sid.address
                        ),
                        shop_account_nr=(
                            hashable_sid[2] if hashable_sid[2] else None
                        ),
                    )
                    if isinstance(sid, dict)
                    else sid
                ),
            )
            for hashable_sid, count in shop_counts.most_common()
            for sid in shop_ids
            if (
                (sid["name"] if isinstance(sid, dict) else sid.name)
                == hashable_sid[0]
                and (
                    Address(**sid["address"]).to_string()
                    if isinstance(sid, dict)
                    and isinstance(sid["address"], dict)
                    else sid.address.to_string()
                )
                == hashable_sid[1]
                and (
                    sid.get("shop_account_nr", "")
                    if isinstance(sid, dict)
                    else (sid.shop_account_nr or "")
                )
                == hashable_sid[2]
            )
        ]

    # Step 1: If category_input is provided, filter to that category
    if category_input:
        return {category_input: category_shop_counts.get(category_input, [])}

    return category_shop_counts


@typechecked
def get_sorted_unique_shop_ids(
    *, previous_shop_ids: Dict[str, List[Tuple[int, ShopId]]]
) -> List[ShopId]:
    # Collect all unique shop IDs with their highest associated integer
    shop_max_scores: Dict[tuple, int] = {}

    for _, tuples in previous_shop_ids.items():
        for score, shop_id in tuples:
            shop_key = (
                shop_id.name,
                shop_id.address.to_string(),
                shop_id.shop_account_nr or "",
            )
            if (
                shop_key not in shop_max_scores
                or score > shop_max_scores[shop_key]
            ):
                shop_max_scores[shop_key] = score

    # Sort shop IDs by score (descending) and name (alphabetical for equal scores)
    sorted_shops = sorted(
        shop_max_scores.keys(),
        key=lambda shop_key: (-shop_max_scores[shop_key], shop_key[0]),
    )

    # Convert back to ShopId objects
    shop_id_map = {
        (sid.name, sid.address.to_string(), sid.shop_account_nr or ""): sid
        for category, tuples in previous_shop_ids.items()
        for _, sid in tuples
    }

    return [
        shop_id_map[shop_key]
        for shop_key in sorted_shops
        if shop_key in shop_id_map
    ]


@typechecked
def filter_receipts_without_address(
    *, labelled_receipts: List[Receipt]
) -> List[Receipt]:
    """Filter out receipts where the shop_identifier.address has all fields set
    to None or empty.

    Args:
        labelled_receipts: List of Receipt objects to filter.

    Returns:
        A list of Receipt objects where the shop_identifier.address has at least one non-None/non-empty field.
    """

    def has_valid_address(shop_id) -> bool:
        """Check if the shop_id's address has at least one non-None/non-empty
        field."""
        if isinstance(shop_id, dict):
            address = shop_id.get("address", {})
            if not isinstance(address, dict):
                return False
            return any(
                field is not None and field != ""
                for field in (
                    address.get("street"),
                    address.get("house_nr"),
                    address.get("zipcode"),
                    address.get("city"),
                    address.get("country"),
                )
            )
        # ShopId object
        address = getattr(shop_id, "address", None)
        if address is None:
            return False
        return any(
            field is not None and field != ""
            for field in (
                address.street,
                address.house_nr,
                address.zipcode,
                address.city,
                address.country,
            )
        )

    return [
        receipt
        for receipt in labelled_receipts
        if has_valid_address(receipt.shop_identifier)
    ]


MAX_ADDRESS_CHOICES = 12


@typechecked
def get_initial_complete_list(
    *, labelled_receipts: List[Receipt], category_input: Optional[str] = None
) -> Tuple[List[str], List[ShopId]]:
    """Generate a hierarchically sorted list of shop address choices.

    Sorting order (all groups sorted by frequency descending):
      1. "manual address" always at index 0.
      2. Exact or sub-category matches (category starts with category_input).
      3. Parent-category matches (shares the top-level prefix).
      4. All remaining addresses.

    At most MAX_ADDRESS_CHOICES entries are returned (including manual
    address), so up to 11 historical addresses.

    Args:
        labelled_receipts: List of Receipt objects.
        category_input: Category to prioritize (e.g., 'groceries:ah').
            If None, all addresses sorted by frequency.

    Returns:
        Tuple of (choice strings, ShopId objects).
    """
    labelled_receipts_with_addresses: List[Receipt] = (
        filter_receipts_without_address(labelled_receipts=labelled_receipts)
    )

    # Get category-to-shop-id mapping with counts.
    previous_shop_ids: Dict[str, List[Tuple[int, ShopId]]] = (
        get_relevant_shop_ids(
            labelled_receipts=labelled_receipts_with_addresses,
            category_input=None,
        )
    )

    # Collect unique shop IDs with total frequency and associated categories.
    shop_freq: Dict[Tuple[str, str, str], int] = {}
    shop_obj: Dict[Tuple[str, str, str], ShopId] = {}
    shop_cats: Dict[Tuple[str, str, str], List[str]] = {}

    for category, tuples in previous_shop_ids.items():
        for count, shop_id in tuples:
            shop_key = (
                shop_id.name,
                shop_id.address.to_string(),
                shop_id.shop_account_nr or "",
            )
            shop_freq[shop_key] = shop_freq.get(shop_key, 0) + count
            shop_obj[shop_key] = shop_id
            if shop_key not in shop_cats:
                shop_cats[shop_key] = []
            if category not in shop_cats[shop_key]:
                shop_cats[shop_key].append(category)

    def freq_sort_key(
        shop_key: Tuple[str, str, str],
    ) -> Tuple[int, str]:
        return (-shop_freq[shop_key], shop_key[0])

    # Partition into tiers based on category_input.
    exact_or_sub: List[Tuple[str, str, str]] = []
    parent_match: List[Tuple[str, str, str]] = []
    rest: List[Tuple[str, str, str]] = []

    if category_input:
        # Parent prefix: e.g. "groceries:" from "groceries:ah"
        parent_prefix = (
            category_input.split(":")[0] + ":"
            if ":" in category_input
            else category_input + ":"
        )

        for shop_key in shop_cats:
            categories = shop_cats[shop_key]
            if any(cat.startswith(category_input) for cat in categories):
                exact_or_sub.append(shop_key)
            elif any(cat.startswith(parent_prefix) for cat in categories):
                parent_match.append(shop_key)
            else:
                rest.append(shop_key)
    else:
        rest = list(shop_cats.keys())

    exact_or_sub.sort(key=freq_sort_key)
    parent_match.sort(key=freq_sort_key)
    rest.sort(key=freq_sort_key)

    # Build result: manual address at index 0, then all historical
    # addresses in tier order.  The visible window (MAX_ADDRESS_CHOICES)
    # is enforced by the scrolling widget, not here — so all addresses
    # remain selectable via arrow-key scrolling.
    choices: List[str] = ["manual address"]
    shop_ids: List[ShopId] = [
        ShopId(name="manual address", address=Address())
    ]

    seen: set = set()
    for shop_key in exact_or_sub + parent_match + rest:
        if shop_key in seen:
            continue
        seen.add(shop_key)
        sid = shop_obj[shop_key]
        choices.append(f"{sid.name}: {sid.address.to_string()}")
        shop_ids.append(sid)

    return choices, shop_ids
