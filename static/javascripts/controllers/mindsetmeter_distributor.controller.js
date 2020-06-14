// Angular controller for the mindsetmeter distributor panel.

/* global util */

angular.module('mskApp').controller('MindsetmeterDistributorCtrl',
  ['$scope', '$timeout', '$document', '$cookieStore', 'Api', 'User', 'ElasticSuggest',
  function ($scope, $timeout, $document, $cookieStore, Api, User, ElasticSuggest) {

    'use strict';

    $scope.$root.loginText = 'CHANGE ME...';
    $scope.$root.signupText = 'CHANGE ME...';

    $scope.assessments = [];
    $scope.surveys = [];
    $scope.groups = [];
    $scope.suggestions = [];

    $scope.$root.loginText = "Log in to use surveys with your participants.";
    $scope.$root.signupText = "Sign up to use surveys with your participants.";

    // For both modals.
    $scope.updating = false;
    $scope.updated = false;
    $scope.errorMessage = '';

    // For create assessment modal.
    $scope.newAssessment = {};
    $scope.assessmentSubmitted = false;

    // For create survey modal.
    $scope.newSurvey = {
      auth_type: 'initials',
      group_name: ''
    };
    $scope.surveySubmitted = false;
    // See assessment.py, url_name_validator()
    var urlName = function (name) {
      return $scope.newAssessment.name ?
        $scope.newAssessment.name
          .toLowerCase()
          .replace(/\s+/g, '-')  // turn chunks of whitespace to single hyphens
          .replace(/[^a-z0-9\-]/g, '') :  // clean out weird characters
        '';
    };

    $scope.$watch('newAssessment.name', function (name) {
      $scope.newAssessment.url_name = urlName(name);
    });

    // Used to populate dropdown in create survey modal.
    $scope.$watch('surveys', function (surveys) {
      $scope.groups = util.arrayUnique(surveys.map(function (s) {
        return s.group_name;
      }));
    });

    $scope.createAssessment = function () {
      $scope.assessmentSubmitted = true;
      $scope.updating = true;
      Api.assessments.create($scope.newAssessment).then(function (response) {
        if (response.error) {
          $scope.updating = false;
          $scope.errorMessage = response.message;
        } else {
          $('#createAssessmentModal').modal('hide');
          var asmt = response.data;
          $scope.assessments.push(asmt);
          $scope.assessmentIndex[asmt.uid] = asmt;
          // Resets 'updating' after modal is fully hidden
          // JQuery hide by default takes 400ms
          $timeout(function () {
            $scope.updating = false;
            // Resets assessment for next creation
            $scope.newAssessment = {};
          }, 400);
        }
      });
    };

    var saveDescriptionRequest;

    $scope.descriptionChange = function (asmt) {
      $timeout.cancel(saveDescriptionRequest);  // if any pending
      saveDescriptionRequest = $timeout(function () {
        saveDescription(asmt);
      }, 500);
    };

    var saveDescription = function (asmt) {
      Api.assessments.update(asmt.uid, {description: asmt.description});
    };

    // Happens at the same time as the create survey modal is opened.
    $scope.setCurrentAssessment = function (asmt) {
      $scope.newSurvey.assessment = asmt.uid;
      // These two are just for the create modal; they're not part of a
      // survey's data model.
      $scope.newSurvey.assessment_name = asmt.name;
      $scope.newSurvey.num_phases = asmt.num_phases;
    };

    $scope.showGroupSuggestions = function () {

      var hideSuggestions = function (event) {
        if (event.target.id !== 'suggestionInput') {
          $scope.hideGroupSuggestions();
          $scope.$apply();
          $document.off('click', hideSuggestions);
        }
      };

      var suggestions = [];
      if ($scope.newSurvey.group_name.length > 0) {
        var elasticSuggestions = ElasticSuggest.basicAutocomplete(
          $scope.newSurvey.group_name, $scope.groups);
        suggestions = suggestions.concat(elasticSuggestions);
      } else {
        suggestions = suggestions.concat($scope.groups);
      }

      if (suggestions.length > 0 && $scope.suggestions.length === 0) {
        $document.on('click', hideSuggestions);
      }

      $scope.suggestions = util.arrayUnique(suggestions);
    };

    $scope.hideGroupSuggestions = function () {
      $scope.suggestions = [];
    };

    $scope.selectGroup = function (group) {
      $scope.newSurvey.group_name = group;
      $scope.hideGroupSuggestions();
    };

    $scope.createSurvey = function () {
      $scope.surveySubmitted = true;
      $scope.updating = true;
      var params = angular.copy($scope.newSurvey);
      delete params.assessment_name; // useful in UI, but not in the data model
      delete params.num_phases; // useful in UI, but not in the data model
      Api.surveys.create(params).then(function (response) {
        if (response.error) {
          $scope.updating = false;
          $scope.errorMessage = response.message;
        } else {
          $('#createSurveyModal').modal('hide');
          var s = response.data;
          s.assessmentName = $scope.assessmentIndex[s.assessment].name;
          $scope.surveys.push(s);
          // Resets 'updating' after modal is fully hidden
          // JQuery hide by default takes 400ms
          $timeout(function () {
            $scope.updating = false;
            $scope.groupInput = '';
          }, 400);
        }
      });
    };

    $scope.loginBeforeCreatingSurvey = function (asmt) {
      $cookieStore.put('msk_mindsetmeter_createSurvey', asmt.uid);
      $scope.showLogin();
    };

    $scope.deleteSurvey = function (survey) {
      if (confirm("Deleting a survey will also delete all collected " +
                  "responses. Are you sure?")) {
        Api.surveys.delete(survey.uid).then(function (response) {
          $scope.surveys.remove(survey);
        });
      }
    };

    var checkPendingActions = function () {
      // If the user wanted to create a survey before logging in, get them
      // started with the modal now.
      var asmtId = $cookieStore.get('msk_mindsetmeter_createSurvey');
      if (asmtId && User.currentUser()) {
        $scope.setCurrentAssessment($scope.assessmentIndex[asmtId]);
        $('#createSurveyModal').modal();
      }
      // In all cases, remove the cookie after page load.
      $cookieStore.remove('msk_mindsetmeter_createSurvey');
    };

    // Populate the UI with assessments.
    Api.assessments.fetchAll().then(function (response) {
      $scope.assessments = response.data || [];

      // For looking up assessment names in survey rows.
      $scope.assessmentIndex = util.indexBy($scope.assessments, 'uid');

      // Populate UI with this user's surveys.
      Api.surveys.fetch().then(function (response) {
        $scope.surveys = response.data || [];
        $scope.surveys.forEach(function (s) {
          s.assessmentName = $scope.assessmentIndex[s.assessment].name;
        });

        // The user may have requested actions, like creating a survey, before
        // logging in.
        checkPendingActions();
      });

    });

  }
]);
