/* global util, JSON */

angular.module('mskApp').directive(
  'surveyRow',
  ['Api', '$timeout', function (Api, $timeout) {
    'use strict';

    var link = function (scope, element, attrs) {

      var saveNoteRequest;
      var noteIndex;

      // For editing survey properties in row.
      scope.surveyAlerts = {
        errorMessage: '',
        updating: false,
        confirmation: false
      };

      var confirmUpdated = function (index) {
        scope.surveyAlerts.confirmation = index;
        $timeout(function () {
          scope.surveyAlerts.confirmation = false;
        }, 1000);
      };

      // Called on ng-change
      scope.noteChange = function (index) {
        noteIndex = index;
        $timeout.cancel(saveNoteRequest);  // if any pending
        // Send the new note to the server to be saved, but only after a delay
        // so the user can finish typing.
        saveNoteRequest = $timeout(saveNotes, 500);
      };

      var saveNotes = function () {
        scope.surveyAlerts.errorMessage = '';
        scope.surveyAlerts.updating = noteIndex;
        var jsonStr = JSON.stringify(scope.survey.json_properties);
        Api.surveys.update(scope.survey.uid, {json_properties: jsonStr})
          .then(function (response) {
            // Give the user a chance to see that the page has saved their
            // work by not hiding the gif for a bit.
            $timeout(function () {
              scope.surveyAlerts.updating = false;
              confirmUpdated(noteIndex);
            }, 500);
            if (response.error) {
              scope.surveyAlerts.errorMessage = response.message;
            }
        });
      };

    };

    return {
      restrict: 'A',
      scope: {
        survey: '='
      },
      link: link,
      templateUrl: '/static/directives/survey_row.html'
    };
  }]
);