from reports.catalog import matching_definitions


def test_ordersatz_variants_are_selected_from_header():
    header = ("Artikel-Nr.", "Bezeichnung 1", "S-Einheit", "Warengruppe", "PG:VK1", "PG:VK2")
    keys = {definition.key for definition in matching_definitions(header)}
    assert "ordersatz-vk1" in keys
    assert "ordersatz-vk2" in keys
    assert "ordersatz-ohne-preise" in keys
    assert "ordersatz-vk3" not in keys
