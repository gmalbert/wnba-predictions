from utils.adapters.odds_api_io import OddsApiIoAdapter
from utils.adapters.therundown import TheRundownAdapter


def test_odds_api_io_normalizes_core_markets():
    adapter = OddsApiIoAdapter(api_key="test")
    rows = adapter._normalize_event(
        {
            "id": 123,
            "home": "Atlanta Dream",
            "away": "Connecticut Sun",
            "date": "2026-09-17T23:30:00Z",
            "bookmakers": {
                "DraftKings": [
                    {"name": "ML", "odds": [{"home": "1.70", "away": "2.20"}]},
                    {"name": "Spread", "odds": [{"hdp": -3.5, "home": "1.91", "away": "1.91"}]},
                    {"name": "Totals", "odds": [{"max": 160.5, "over": "1.90", "under": "1.90"}]},
                ]
            },
        }
    )

    assert len(rows) == 6
    assert {row["market"] for row in rows} == {"h2h", "spreads", "totals"}
    assert {row["price"] for row in rows if row["market"] == "h2h"} == {-143, 120}
    assert {row["point"] for row in rows if row["market"] == "totals"} == {160.5}
    assert all(row["source"] == "odds_api_io" for row in rows)


def test_therundown_normalizes_core_markets_and_ignores_off_board_price():
    adapter = TheRundownAdapter(api_key="test")
    rows = adapter._normalize_event(
        {
            "event_id": "abc",
            "teams": [{"name": "Connecticut Sun"}, {"name": "Atlanta Dream"}],
            "schedule": {"start_time": "2026-09-17T23:30:00Z"},
            "markets": [
                {
                    "market_id": 1,
                    "participants": [
                        {"name": "Atlanta Dream", "lines": [{"prices": {"19": {"price": -110}}}]},
                        {"name": "Connecticut Sun", "lines": [{"prices": {"19": {"price": 0.0001}}}]},
                    ],
                },
                {
                    "market_id": 2,
                    "participants": [
                        {"name": "Atlanta Dream", "lines": [{"value": -3.5, "prices": {"19": {"price": -110}}}]},
                    ],
                },
                {
                    "market_id": 3,
                    "participants": [
                        {"name": "Over", "lines": [{"value": 160.5, "prices": {"19": {"price": -110}}}]},
                    ],
                },
            ],
        }
    )

    assert len(rows) == 3
    assert {row["market"] for row in rows} == {"h2h", "spreads", "totals"}
    assert all(row["book"] == "DraftKings" for row in rows)
    assert all(row["source"] == "therundown" for row in rows)
