"""Reading harm out of the reporting."""
import stakes


def _members(*titles):
    return [{"title": t, "snippet": ""} for t in titles]


def test_a_story_reporting_no_harm_scores_the_floor_not_zero():
    """The overall score is multiplicative, so zero would DELETE a story."""
    score, n = stakes.stakes(_members(
        "NASA launches first telescope named after female scientist"))
    assert score == stakes.FLOOR and n == 0
    assert stakes.FLOOR > 0.5, "the floor has to leave quiet-day news able to lead"


def test_word_numbers_count():
    assert stakes.casualties("Eight killed after ferry capsizes off Cyprus") == 8


def test_an_age_in_apposition_is_not_a_body_count():
    """This was the bug that made one shooting rate as high as a ferry disaster:
    the digit run swallowed its own trailing comma, so 'Woman, 22, killed' read
    as twenty-two dead."""
    assert stakes.casualties(
        "Manhunt after shooting at Swiss rave kills woman, 22, and injures five") == 0


def test_a_year_is_not_a_body_count():
    assert stakes.casualties("Anniversary of the 2001 attacks; no one injured") == 0


def test_thousands_separators_survive():
    assert stakes.casualties("more than 3,000 missing in Nepal") == 3000


def test_the_toll_is_taken_from_the_outlet_reporting_the_most():
    """Early wire copy undercounts and the figure climbs all day, so the maximum
    across outlets is the freshest number, not an outlier."""
    n = stakes.casualties("Eight killed and 17 missing. At least 22 missing, "
                          "officials say.")
    assert n == 22


def test_more_deaths_score_higher_but_not_proportionally():
    one, _ = stakes.stakes(_members("1 dead in a shooting"))
    many, _ = stakes.stakes(_members("Death toll nears 800 after glacier collapse"))
    assert stakes.FLOOR < one < many <= 1.0
    # Log-scaled on purpose: linear would let one enormous event flatten every
    # other story for days.
    assert (many - stakes.FLOOR) < 800 * (one - stakes.FLOOR)


def test_score_never_leaves_the_unit_interval():
    for t in ("2,000,000 dead", "1 injured", "nothing happened here",
              "dozens missing", "hundreds of thousands displaced"):
        score, _ = stakes.stakes(_members(t))
        assert stakes.FLOOR <= score <= 1.0, t
