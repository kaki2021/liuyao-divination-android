"""Solar-clock boundaries and legacy calendar compatibility, all offline."""
import copy
from datetime import datetime, timedelta
import unittest
from .calendar_context import calculate_calendar
from .solar_time import solar_clock, equation_of_time
from .pipeline import calculate_chart
from validate_input import validate_input


def solar(value,longitude=104.06):
    return calculate_calendar({'actual_cast_time':value,'time_basis':'true_solar','cast_location':{'longitude':longitude}})


class SolarTimeChecks(unittest.TestCase):
    def test_unknown_solar_time_can_be_recorded_without_inventing_location(self):
        data={'question':'问题','lines':['young_yang']*6,'time_basis':'true_solar'}
        self.assertTrue(validate_input(data)['valid'])
        result=calculate_calendar(data)
        self.assertEqual(result['status'],'missing')
        self.assertEqual(result['time_basis'],'true_solar')
        self.assertNotIn('北京时间',result['convention_label'])
        self.assertFalse(validate_input({**data,'actual_cast_time':'2026-10-24T12:00:00+08:00'})['valid'])

    def test_equation_of_time_has_correct_sign_and_seasonal_scale(self):
        # Known annual extrema: about -14 min in February, +16 min in November.
        self.assertAlmostEqual(equation_of_time(datetime.fromisoformat('2024-02-11T12:00:00+00:00')),-14.2,delta=.4)
        self.assertAlmostEqual(equation_of_time(datetime.fromisoformat('2024-11-03T12:00:00+00:00')),16.5,delta=.4)

    def test_east_longitude_is_ahead_and_timezones_do_not_change_instant(self):
        utc=datetime.fromisoformat('2026-10-24T04:00:00+00:00')
        east,eq=solar_clock(utc,120);west,_=solar_clock(utc,105)
        self.assertEqual(east-west,timedelta(hours=1))
        self.assertEqual(solar_clock(utc,120),solar_clock(utc.astimezone(datetime.fromisoformat('2026-10-24T12:00:00+08:00').tzinfo),120))
        self.assertAlmostEqual((east-utc.replace(tzinfo=None)).total_seconds()/60,480+eq,places=6)

    def test_solar_midnight_changes_day_and_six_spirits(self):
        original='2023-02-25T00:10:00+08:00'
        result=solar(original)
        self.assertTrue(result['cast_time'].startswith('2023-02-24T22:'))
        self.assertEqual(result['pillars']['day'],'癸丑')
        self.assertEqual(result['pillars']['hour'],'癸亥')
        chart=calculate_chart({'lines':['young_yang']*6,'actual_cast_time':original,
            'time_basis':'true_solar','cast_location':{'longitude':104.06}},include_experimental=False)
        self.assertEqual(chart['main']['lines'][0]['six_spirit'],'玄武')
        self.assertNotEqual(result['pillars']['day'],calculate_calendar({'actual_cast_time':original})['pillars']['day'])

    def test_solar_late_zi_retains_current_day_but_uses_next_day_hour(self):
        result=solar('2023-02-25T00:30:00+08:00')
        self.assertTrue(result['cast_time'].startswith('2023-02-24T23:'))
        self.assertEqual(result['pillars']['day'],'癸丑')
        self.assertEqual(result['pillars']['hour'],'甲子')

    def test_term_boundary_uses_actual_instant_even_when_solar_clock_is_before_term(self):
        before=solar('2012-09-07T13:29:00+08:00')
        after=solar('2012-09-07T13:29:01+08:00')
        self.assertEqual(before['pillars']['month'],'戊申')
        self.assertEqual(after['pillars']['month'],'己酉')
        self.assertLess(after['cast_time'],'2012-09-07T13:29:01')

    def test_lichun_year_and_month_change_at_real_second_in_all_longitudes(self):
        for longitude in (-150,0,104.06,150):
            before=solar('2024-02-04T16:27:06+08:00',longitude)
            after=solar('2024-02-04T16:27:07+08:00',longitude)
            self.assertEqual([before['pillars'][k] for k in ('year','month')],['癸卯','乙丑'])
            self.assertEqual([after['pillars'][k] for k in ('year','month')],['甲辰','丙寅'])

    def test_solar_metadata_is_explicit_and_source_location_is_not_mutated(self):
        data={'actual_cast_time':'2026-10-24T04:00:00Z','time_basis':'true_solar',
              'cast_location':{'longitude':104.06,'latitude':30.67,'source':'device','accuracy_m':200}}
        before=copy.deepcopy(data);result=calculate_calendar(data)
        self.assertEqual(data,before);self.assertIsNone(result['timezone'])
        self.assertNotIn('+08:00',result['cast_time'])
        self.assertEqual(result['beijing_cast_time'],'2026-10-24T12:00:00+08:00')
        self.assertTrue(result['calculation_policy']['true_solar_time'])
        self.assertEqual(result['solar_time']['longitude_correction_minutes'],-63.76)

    def test_legacy_inputs_and_explicit_beijing_are_identical(self):
        data={'actual_cast_time':'2023-02-24T23:30:00+08:00'}
        self.assertEqual(calculate_calendar(data),calculate_calendar({**data,'time_basis':'beijing_standard'}))

    def test_unknown_time_and_invalid_location_do_not_invent_a_calendar(self):
        self.assertEqual(solar(None)['status'],'missing')
        self.assertEqual(calculate_calendar({'actual_cast_time':'2026-01-01T00:00:00Z','time_basis':'true_solar'})['code'],'CAST_LOCATION_REQUIRED')
        for longitude in (181,-181,float('nan'),float('inf'),True,'104'):
            self.assertEqual(solar('2026-01-01T00:00:00Z',longitude)['status'],'error')
            self.assertFalse(validate_input({'question':'问题','lines':['young_yang']*6,'time_basis':'true_solar','cast_location':{'longitude':longitude}})['valid'])


if __name__=='__main__':unittest.main()
