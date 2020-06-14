// Angular controller for the mindsetmeter survey entry page.

/* global util */

angular.module('mskApp').controller('EnterSurveyCtrl',
  ['$scope', '$window', 'Api', 'User',
  function ($scope, $window, Api, User) {

    'use strict';

    $scope.mode = 'entry_code';  // can switch to 'ids', 'initials', or 'msk'

    var entryCodePattern = /^([a-z]+ +[a-z]+) +(\d)$/;  // two words + digit
    $scope.months = ["January", "February", "March", "April", "May", "June",
                     "July", "August", "September", "October", "November",
                     "December"];
    $scope.daysPerMonth = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

    var survey,
        phase,
        publicKey;
    $scope.entryCode = '';
    $scope.entryCodeValid = false;
    $scope.entryCodePatternValid = true;
    $scope.entryCodeSubmitted = false;

    // For the kind of identification where participants type in arbitrary
    // text, like email addresses. This pattern is almost certainly overkill,
    // but that's a detail for now.
    // ASCII, non whitespace, non control. See octal values on asciitable.com.
    $scope.identifierPattern = /^[\041-\176]{5,}$/;

    // User has typed a code, like "epic shark 1", and clicked next, so look
    // up the appropriate survey and go to the next page.
    // This  function refers to "phase codes" when it includes the phase digit,
    // and "entry codes" when it does not.
    $scope.submitCode = function () {
      $scope.entryCodeValid = false;
      $scope.entryCodePatternValid = true;

      // Make sure it follows the pattern.
      var phaseCode = $scope.phaseCode.toLowerCase();
      if (!entryCodePattern.test(phaseCode)) {
        $scope.entryCodePatternValid = false;  // triggers UI hint
        return;
      }

      // Extract important parts.
      var parts = entryCodePattern.exec(phaseCode);
      var entryCode = parts[1];
      phase = parseInt(parts[2], 10);  // counts from 1

      // Look up the survey based on the code.
      Api.surveyCodes.fetch(entryCode).then(function (response) {
        $scope.entryCodeSubmitted = true;
        if (response.error) {
          // @todo: not sure how to handle this case.
          console.error(response.message);
        } else if (!response.data) {
          // No matching survey
          // @todo: special message here?
        } else {
          $scope.entryCodeValid = true;
          survey = response.data;

          // Check the phase is valid for this survey.
          var validPhases = util.rangeInclusive(1, survey.public_keys.length);
          if (!validPhases.contains(phase)) {
            // @todo: special message here?
            throw new Error("Invalid phase");
          }

          // Look up the public key for this phase.
          publicKey = survey.public_keys[phase - 1];

          // Now to identify the participant. If they're signed in to the MSK,
          // we can use that.
          $scope.user = User.currentUser();
          if ($scope.user) {
            $scope.mode = 'msk';
          } else {
            // Otherwise, show them an identification page, per the survey
            // configuration.
            $scope.mode = survey.auth_type;
          }
        }
      });
    };

    // Turns initials CAM, born in November, on the 19th, into "CAM.11.19"
    var getIdFromInitials = function () {
      // from counts-from-zero to -from-one
      var birthMonth = parseInt($scope.birthMonth, 10) + 1,
          // ensure two digits with leading zeros
          mon = (birthMonth < 10 ? '0' : '') + birthMonth,
          day = ($scope.birthDay < 10 ? '0' : '') + $scope.birthDay;
      return [$scope.initials, mon, day].join('.');
    };

    // User has clicked Next on any of the identification pages. Hash their
    // id if necessary and send them to MM1 on survey.perts.net.
    $scope.submitIdentifier = function () {
      if ($scope.mode === 'msk') {
        redirectToMindsetmeter($scope.user.uid);
        return;  // the redirect will stop execution, but just for clarity...
      }

      if ($scope.mode === 'initials') {
        $scope.id = getIdFromInitials();
      }  // else for mode 'ids', $scope.id set directly from input

      if (!$scope.identifierPattern.test($scope.id)) {
        throw new Error("bad identifier: " + $scope.id);
      }

      // Ids that aren't MSK user ids should be hashed before continuing.
      Api.hashMmId($scope.id).then(function (response) {
        if (response.error) {
          // @todo: not sure how to handle this case.
          console.error(response.message);
        } else {
          redirectToMindsetmeter(response.data);
        }
      });
    };

    var redirectToMindsetmeter = function (pid) {
      // pid is for "participant identifier"
      var url = 'http://survey.perts.net/take/' + survey.url_name +
        '?phase=' + phase +
        '&public_key=' + publicKey +
        '&pid=' + pid;
      $window.location.href = url;
    };
  }]
);
