// Angular controller for profile pages

/* global util */

angular.module('mskApp')
  .controller('ProfileCtrl', ['$scope', 'Api', 'User', '$window',
    function ($scope, Api, User, $window) {

    'use strict';

    $scope.practices = [];
    $scope.loading = true;
    $scope.password = '';
    $scope.repeatPassword = '';
    $scope.updating = false;
    $scope.updated = false;
    $scope.errorMessage = '';
    $scope.resultType = 'practices';
    // Used for pagination
    $scope.pageSize = 20;
    $scope.page = 0;
    $scope.shouldPaginate = false;


    $scope.init = function(user) {
      if (user) {

        $scope.profileUser = user;
        $scope.fetchResults();

      } else {

        // Update user once it's been fetched.
        $scope.$on('user:updated', function(event, data) {

          $scope.profileUser = User.currentUser();

          // Fetch practices if a user is found.
          if ($scope.profileUser) {
            $scope.fetchResults();
          }

        });

      }
    };

    $scope.setResultType = function (type) {

      // Reset variables
      $scope.resultType = type;
      $scope.practices = [];
      $scope.noPractices = false;
      $scope.noLikes = false;

      $scope.fetchResults();
    };

    $scope.fetchResults = function () {

      $scope.loading = true;
      $scope.shouldPaginate = false;

      var functionName;

      if ($scope.resultType === 'practices') {
        functionName = 'fetchPractices';
      } else if ($scope.resultType === 'likes') {
        functionName = 'fetchVotes';
      }

      Api.users[functionName]($scope.profileUser, $scope.page)
        .then(function (response) {

          $scope.loading = false;

          if (response.data && response.data.length > 0) {

            // Handle pagination if page past 0
            if ($scope.page < 1) {
              $scope.practices = response.data;
            } else {
              $scope.practices = $scope.practices.concat(response.data);
            }

            forEach($scope.practices, function (result) {
              if(Array.isArray(result.tags)) {
                result.array = true;
              }
            });

            if (response.data.length >= $scope.pageSize) {
              $scope.shouldPaginate = true;
            }

          } else if ($scope.page < 1) {
            if ($scope.resultType === 'practices') {
              $scope.noPractices = true;
            } else if ($scope.resultType === 'likes') {
              $scope.noLikes = true;
            }
          }
        }, function(error) {
          // Error!
        });
    };

    // Loads more results without changing query

    $scope.loadMore = function() {

      $scope.page += 1;
      $scope.fetchResults();

    };

    $scope.deletePractice = function (practice) {

      // Confirm and delete!

      if (confirm('Are you sure you want to delete this?')) {
        Api.practices.delete(practice)
          .then(function (response) {
            // Remove practice from UI
            var index = $scope.practices.indexOf(practice);
            $scope.practices.splice(index, 1);
          });
      }

    };

    $scope.editPractice = function (practice) {

      // Send to edit page
      // @todo: add Mixpanel tracking!!

      $window.location.href = '/practices/edit/' + practice.short_uid;

    };

    // Username regex... unused at the moment.
    var userRegex = new RegExp('[A-Za-z0-9\_\-]*');

    $scope.updateInfo = function (isValid) {

      $scope.submitted = true;

      if (isValid) {

        $scope.errorMessage = '';

        //@todo: check for the username to be valid!!!!

        if ($scope.profileUser) {

          var params = {};
          params.first_name = $scope.profileUser.first_name;
          params.last_name = $scope.profileUser.last_name;
          params.email = $scope.profileUser.email;
          params.username = $scope.profileUser.username;
          params.short_bio = $scope.profileUser.short_bio;
          params.receives_updates = $scope.profileUser.receives_updates;

          $scope.updating = true;

          Api.users.update($scope.profileUser, params)
            .then(function (response) {

              if (response.error) {
                $scope.updating = false;

                if (response.message.contains('DuplicateEmail')) {
                  $scope.errorMessage = 'Email already in use.';
                  $scope.userForm.email.$setValidity('email', false);
                } else if (response.message.contains('InvalidUsername')) {
                  $scope.errorMessage = 'Username can only contain letters, numbers, _\'s and -\'s.';
                  $scope.userForm.username.$setValidity('username', false);
                } else if (response.message.contains('DuplicateUsername')) {
                  $scope.errorMessage = 'Username already in use.';
                  $scope.userForm.username.$setValidity('username', false);
                } else {
                  $scope.errorMessage = 'Error with data. Try again.';
                }
              } else {

                if ($scope.file) {
                  $scope.uploadImage();
                } else {
                  $window.location.reload();
                }
              }
            });
        }

      } else {
        $scope.errorMessage = 'Missing or invalid parameters.';
      }

    };

    $scope.uploadImage = function() {

      $scope.uploading = true;

      Api.users.uploadImage($scope.file)
        .then(function (response) {
          $scope.uploading = false;
          $window.location.reload();
        }, function (error) {
          $scope.error = 'Error uploading image, try another.';
          $scope.uploading = false;
        });

    };

    // Opens password update modal

    $scope.showPasswordModal = function() {
      $('#editModal').modal('toggle');
      $('#passwordModal').modal('toggle');
      $scope.errorMessage = '';
    };

    // Updates password

    $scope.updatePassword = function (isValid) {

      $scope.submitted = true;

      if (isValid) {

        $scope.errorMessage = '';

        var params = {};

        if ($scope.password.length > 0) {
          if ($scope.repeatPassword === $scope.password) {
            params.password = $scope.password;
          } else {
            $scope.password = '';
            $scope.repeatPassword = '';
            $scope.errorMessage = 'Passwords do not match.';
            return;
          }
        }

        $scope.updating = true;

        Api.users.update($scope.profileUser, params)
          .then(function (response) {

            if (response.error) {
              $scope.updating = false;

              if (response.message.contains('BadPassword')) {
                $scope.errorMessage = 'At least 8 characters, ASCII only.';
              } else {
                $scope.errorMessage = 'Error with data. Try again.';
              }
            } else {
              $window.location.reload();
            }
          });

      } else {
        $scope.errorMessage = 'Missing or invalid parameters.';
      }

    };

    $scope.isPractice = function (content) {

      return (util.getKind(content.uid) === 'Practice');

    };

  }]);
