from collections import Counter
from typing import Dict, List, Optional, Tuple

from hledger_preprocessor.TransactionObjects.Address import Address
from hledger_preprocessor.TransactionObjects.Receipt import Receipt
from hledger_preprocessor.TransactionObjects.ShopId import ShopId
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

    def has_valid_address(shop_id: dict) -> bool:
        """Check if the shop_id's address has at least one non-None/non-empty
        field."""
        # Get the address dictionary, default to empty dict if not present
        address = shop_id.get("address", {})
        # Ensure address is a dictionary; if not, treat as invalid
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

    return [
        receipt
        for receipt in labelled_receipts
        if has_valid_address(receipt.shop_identifier)
    ]


@typechecked
def get_initial_complete_list(
    *, labelled_receipts: List[Receipt], category_input: Optional[str] = None
) -> Tuple[List[str], List[ShopId]]:
    """Generate a list of shop choices with starred entries for the specified
    category, followed by non-starred entries, with 'manual address' at the
    top.

    Args:
        labelled_receipts: List of Receipt objects.
        category_input: Category to prioritize (e.g., 'groceries'). If None, no starring.

    Returns:
        Tuple[List[str], List[ShopId]]: A tuple containing the list of choice strings
        (with stars for matching category) and the corresponding list of ShopId objects.

    Raises:
        ValueError: If labelled_receipts list is empty.
    """
    # if not labelled_receipts:
    #     raise ValueError("Receipts list cannot be empty")

    labelled_receipts_with_addresses: List[Receipt] = (
        filter_receipts_without_address(labelled_receipts=labelled_receipts)
    )

    # Get category-to-shop-id mapping with counts
    previous_shop_ids: Dict[str, List[Tuple[int, ShopId]]] = (
        get_relevant_shop_ids(
            labelled_receipts=labelled_receipts_with_addresses,
            category_input=None,
        )
    )

    # Collect all unique shop IDs with their highest score and associated category
    shop_info: Dict[
        Tuple[str, str, Optional[str]], Tuple[int, ShopId, List[str]]
    ] = {}
    for category, tuples in previous_shop_ids.items():
        for score, shop_id in tuples:
            shop_key = (
                shop_id.name,
                shop_id.address.to_string(),
                shop_id.shop_account_nr or "",
            )
            if shop_key not in shop_info or score > shop_info[shop_key][0]:
                # Store the highest score, shop_id, and list of associated categories
                shop_info[shop_key] = (score, shop_id, [category])
            elif shop_key in shop_info and score == shop_info[shop_key][0]:
                # Add category to existing entry if score is equal
                shop_info[shop_key][2].append(category)

    # Separate shops into starred (matching category_input) and non-starred groups
    starred_shops: List[Tuple[int, ShopId, List[str]]] = []
    non_starred_shops: List[Tuple[int, ShopId, List[str]]] = []

    for shop_key, (score, shop_id, categories) in shop_info.items():
        entry = (score, shop_id, categories)
        if category_input and category_input in categories:
            starred_shops.append(entry)
        else:
            non_starred_shops.append(entry)

    # Sort both groups by score (descending) and name (alphabetically)
    def sort_key(entry: Tuple[int, ShopId, List[str]]) -> Tuple[int, str]:
        return (-entry[0], entry[1].name)

    starred_shops.sort(key=sort_key)
    non_starred_shops.sort(key=sort_key)

    # Create choice strings and shop_ids list
    choices: List[str] = ["manual address"]
    shop_ids: List[ShopId] = [
        ShopId(name="manual address", address=Address())
    ]  # Placeholder ShopId

    # Add starred shops (with * prefix)
    for score, shop_id, _ in starred_shops:
        choice_str = f"*{shop_id.name}: {shop_id.address.to_string()}"

        choices.append(choice_str)
        shop_ids.append(shop_id)

    # Add non-starred shops
    for score, shop_id, _ in non_starred_shops:
        choice_str = f"{shop_id.name}: {shop_id.address.to_string()}"
        choices.append(choice_str)
        shop_ids.append(shop_id)

    return choices, shop_ids
