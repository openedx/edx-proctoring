// This dropdown component was borrowed from
// https://github.com/edx/edx-platform/blob/master/lms/static/js/dashboard/dropdown.js.
// It has been slightly modified to fit the needs of the edx-proctoring library.
edx = edx || {};

(function($) {
    'use strict';

    var keyCodes = {
        TAB: 9,
        ESCAPE: 27,
        SPACE: 32,
        ARROWUP: 38,
        ARROWDOWN: 40
    };

    edx.dashboard = edx.dashboard || {};
    edx.dashboard.dropdown = {};

    edx.dashboard.dropdown.toggleExamAttemptActionDropdownMenu = function(event) {
        var $target = $(event.currentTarget),
            dashboardIndex = $target.data().dashboardIndex,
            $dropdown = $($target.data('dropdownSelector') || '#actions-dropdown-' + dashboardIndex),
            $dropdownButton = $($target.data('dropdownButtonSelector') || '#actions-dropdown-link-' + dashboardIndex),
            ariaExpandedState = ($dropdownButton.attr('aria-expanded') === 'true'),
            menuItems = $dropdown.find('a');

        var catchKeyPress = function(object, keyPressEvent) {
            // get currently focused item
            var $focusedItem = $(':focus');

            // get the index of the currently focused item
            var focusedItemIndex = menuItems.index($focusedItem);

            // var to store next focused item index
            var itemToFocusIndex;

            // if space or escape key pressed
            if (keyPressEvent.which === keyCodes.SPACE || keyPressEvent.which === keyCodes.ESCAPE) {
                $dropdownButton.click();
                keyPressEvent.preventDefault();
            } else if (keyPressEvent.which === keyCodes.AWRROWUP ||
                (keyPressEvent.which === keyCodes.TAB && keyPressEvent.shiftKey)) {
                // if up arrow key pressed or shift+tab
                // if first item go to last
                if (focusedItemIndex === 0 || focusedItemIndex === -1) {
                    menuItems.last().focus();
                } else {
                    itemToFocusIndex = focusedItemIndex - 1;
                    menuItems.get(itemToFocusIndex).focus();
                }
                keyPressEvent.preventDefault();
            } else if (keyPressEvent.which === keyCodes.ARROWDOWN || keyPressEvent.which === keyCodes.TAB) {
                // if down arrow key pressed or tab key
                // if last item go to first
                if (focusedItemIndex === menuItems.length - 1 || focusedItemIndex === -1) {
                    menuItems.first().focus();
                } else {
                    itemToFocusIndex = focusedItemIndex + 1;
                    menuItems.get(itemToFocusIndex).focus();
                }
                keyPressEvent.preventDefault();
            }
        };

        // Toggle the visibility control for the selected element and set the focus
        $dropdown.toggleClass('is-visible');
        if ($dropdown.hasClass('is-visible')) {
            $dropdown.attr('tabindex', -1);
            $dropdown.focus();
        } else {
            $dropdown.removeAttr('tabindex');
            $dropdownButton.focus();
        }

        // Inform the ARIA framework that the dropdown has been expanded
        $dropdownButton.attr('aria-expanded', !ariaExpandedState);

        // catch keypresses when inside dropdownMenu (we want to catch spacebar;
        // escape; up arrow or shift+tab; and down arrow or tab)
        $dropdown.on('keydown', function(e) {
            catchKeyPress($(this), e);
        });
    };

    edx.dashboard.dropdown.bindToggleButtons = function(selector) {
        $(selector).bind(
            'click',
            edx.dashboard.dropdown.toggleExamAttemptActionDropdownMenu
        );
    };

    $(document).ready(function() {
        edx.dashboard.dropdown.bindToggleButtons('.action-more');
    });
}(jQuery));
