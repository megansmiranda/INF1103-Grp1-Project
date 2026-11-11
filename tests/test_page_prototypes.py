"""Single-choice diet forms and legacy profile compatibility."""
import re
import pytest
from werkzeug.datastructures import MultiDict

from conftest import SUGAR_MAX_10
from test_web import Browser, build_app
from test_dietary_followup import SIGNUP
from nutrilenz.data.mapper import RecordMapper
from nutrilenz.domain.user import User
from nutrilenz.domain.dietary_check_factory import DietaryCheckFactory
from nutrilenz.errors.validation_error import ValidationError
from nutrilenz.web.forms import FormParser


@pytest.mark.parametrize('diets', [['vegan', 'vegetarian'], ['vegetarian_no_dairy', 'vegetarian'],
                                   ['vegan', 'vegetarian_no_dairy'], ['none', 'vegan'], ['vegan', 'vegan']])
def test_form_rejects_multiple_radio_values(diets):
    with pytest.raises(ValidationError, match='Choose only one diet'):
        FormParser().dietary_checks(MultiDict([('diet', diet) for diet in diets]))


@pytest.mark.parametrize('diet', ['none', *DietaryCheckFactory.DIETS])
def test_radio_and_independent_checks_round_trip(diet):
    browser = Browser(build_app())
    response = browser.post('/signup', dict(SIGNUP, diet=diet, dietary_checks=['egg', 'halal_friendly']))
    assert response.status_code == 302
    html = browser.get('/profile').get_data(as_text=True)
    assert re.search(r'name="diet" value="' + diet + r'"\s+checked', html)
    for key in ['egg', 'halal_friendly']:
        assert re.search(r'name="dietary_checks" value="' + key + r'"\s+checked', html)
    browser.post('/profile', dict(SIGNUP, diet='none', dietary_checks=[]))
    html = browser.get('/profile').get_data(as_text=True)
    assert re.search(r'name="diet" value="none"\s+checked', html)
    assert not re.search(r'name="dietary_checks"[^>]*checked', html)


@pytest.mark.parametrize('endpoint', ['/signup', '/profile'])
def test_validation_keeps_radio_ticks_and_avoid(endpoint):
    browser = Browser(build_app())
    if endpoint == '/profile':
        browser.login()
    response = browser.post(endpoint, dict(SIGNUP, target_REDUCE_SUGAR='bad', diet='vegetarian_no_dairy',
                                          dietary_checks=['egg', 'nuts']))
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert re.search(r'name="diet" value="vegetarian_no_dairy"\s+checked', html)
    assert re.search(r'name="dietary_checks" value="egg"\s+checked', html)
    assert re.search(r'name="dietary_checks" value="nuts"\s+checked', html)
    assert 'value="palm oil"' in html


@pytest.mark.parametrize('values', [{'diet': ['vegan', 'vegetarian']}, {'diet': 'invented'},
                                  {'diet': 'none', 'dietary_checks': ['vegan']}])
@pytest.mark.parametrize('endpoint', ['/signup', '/profile'])
def test_tampered_diet_rejected_on_both_pages(endpoint, values):
    browser = Browser(build_app())
    if endpoint == '/profile':
        browser.login()
    assert browser.post(endpoint, dict(SIGNUP, **values)).status_code == 400


@pytest.mark.parametrize('keys,expected', [
    (['vegetarian', 'vegan', 'egg'], ['vegan', 'egg']),
    (['vegetarian_no_dairy', 'vegetarian', 'nuts'], ['vegetarian_no_dairy', 'nuts']),
    (['vegan', 'vegetarian_no_dairy', 'vegetarian', 'halal_friendly'], ['vegan', 'halal_friendly'])])
def test_saved_multiple_diets_load_strictest_and_warn(keys, expected, caplog):
    mapper = RecordMapper()
    row = mapper.user_to_row(User('old', 'hash', [SUGAR_MAX_10], user_id=17))
    row['dietary_checks'] = keys
    loaded = mapper.user_from_row(row)
    assert [check.key for check in loaded.profile.dietary_checks] == expected
    assert 'User 17 has multiple saved diets' in caplog.text
    assert row['dietary_checks'] == keys  # loading does not rewrite stored data


def test_signup_sections_and_no_diet_default():
    html = Browser(build_app()).get('/signup').get_data(as_text=True)
    assert html.count('type="radio" name="diet"') == 4
    assert re.search(r'name="diet" value="none"\s+checked', html)
    assert html.count('name="avoid_ingredients"') == 1
    assert html.index('>1</span>') < html.index('>2</span>') < html.index('>3</span>')
    assert 'Allergens \u00b7 tick any' in html
    assert "Don't eat eggs? Also tick Egg below." not in html
    diet_section = re.search(r'<fieldset class="dietary-group">(.*?)</fieldset>', html, re.S).group(1)
    assert 'type="checkbox" name="dietary_checks" value="halal_friendly"' in diet_section
    assert diet_section.index('value="vegan"') < diet_section.index('value="halal_friendly"')
    assert 'Also flags pork, gelatine and alcohol words.' in diet_section
    allergens = re.findall(r'<fieldset class="dietary-group">(.*?)</fieldset>', html, re.S)[1]
    assert re.findall(r'value="([^"]+)"', allergens) == ['nuts', 'dairy', 'gluten', 'egg', 'soy', 'shellfish']
