angular.module('mskApp')
  .directive('searchResult', ['$window', 'Api', function ($window, Api, User) {
    'use strict';

    return {
      restrict: 'E',
      replace: true,
      transclude: true,
      scope: {
        result: '=',
        profileResult: '=',
        isYours: '='
      },
      templateUrl: '/static/directives/search_result.html',

      link: function(scope, element, attrs) {

        scope.result.createdPrettyDate = util.prettyDate(scope.result.created);
        scope.kind = util.getKind(scope.result.uid);

        // Use 'rejected' to show user if their own practice was rejected
        if (scope.profileResult && scope.isYours && scope.kind === 'Practice') {
          scope.rejected = (!scope.result.pending && !scope.result.listed);
        } else {
          
        }

        // Create user link if username is properly made
        if (scope.result.user && scope.result.user.username) {
          scope.userLink = '/users/' + scope.result.user.canonical_username;
        }

        // Determine type by look at content_type
        if (Array.isArray(scope.result.content_type)) {
          angular.forEach(scope.result.content_type, function(type) {
            if (type === 'video') { scope.isVideo = true; }
            if (type === 'files') { scope.hasFiles = true; }
          });
        } else {
          if (scope.result.content_type === 'video') { scope.isVideo = true; }
          if (scope.result.content_type === 'files') { scope.hasFiles = true; }
        }

        // Determine linking based on kind of content
        if (scope.kind === 'Practice') {
          scope.link = '/practices/' + scope.result.short_uid;
        } else if (scope.kind === 'Lesson') {
          scope.link = null;
        }

        // Function to pull course paths
        scope.loadCourses = function() {
          if (scope.kind === 'Lesson' && !scope.loadingCourses) {

            scope.loadingCourses = true;

            Api.lessons.getThemes(scope.result)
              .then( function (response) {

                if (response.data && response.data.length) {

                  if (response.data.length === 1) {
                    $window.location.href = response.data[0].lesson_link;
                  } else {
                    scope.courses = response.data;
                    scope.link = scope.courses[0].lesson_link;
                    scope.loadingCourses = false;
                    scope.coursesFound = true;
                  }
                }

              });

          } else {
            // Error!
          }
        };
      }
    };
  }]);
