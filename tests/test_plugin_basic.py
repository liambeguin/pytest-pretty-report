def test_marker_is_registered(pytester):
    pytester.makepyfile(
        '''
        import pretty_report

        @pretty_report.slow()
        def test_a():
            pass
        '''
    )
    result = pytester.runpytest('--strict-markers')
    result.assert_outcomes(passed=1)
