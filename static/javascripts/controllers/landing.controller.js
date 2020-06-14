// Angular controller for handling practices on landing page

angular.module('mskApp')
	.controller('LandingCtrl', ['$scope', 'Api',
		function ($scope, Api) {

		'use strict';

		$scope.popularPractices = [];

    Api.practices.fetchPopular().then( function(response) {

      $scope.popularPractices = response.data;

    });

    $scope.topics = {};
    $scope.topics.gmsForEducators = [
      {
        link: '/topics/about-growth-mindset',
        title: 'About Growth Mindset',
        description: 'Learn about what a growth mindset is and why it’s important.',
        imgSrc: "/static/images/topics/thumbnail-about-growth-mindset.png",
        imgAlt: "About Growth Mindset",
      },
      {
        link: '/topics/teaching-growth-mindset',
        title: 'Teaching a Growth Mindset',
        description: 'Learn how to talk to students about the brain, and download a growth mindset lesson plan.',
        imgSrc: "/static/images/topics/thumbnail-teaching-growth-mindset.png",
        imgAlt: "Teaching a Growth Mindset",
      },
      {
        link: '/topics/praise-process-not-person',
        title: 'Praise the Process, Not the Person',
        description: 'Learn about the kind of praise that promotes a growth mindset, and see it in action.',
        imgSrc: "/static/images/topics/thumbnail-praise-process-not-person.png",
        imgAlt: "Praise the Process, Not the Person",
      },
      {
        link: '/topics/celebrate-mistakes',
        title: 'Celebrate Mistakes',
        description: 'Learn how to promote mistakes from Carol Dweck and Jo Boaler; watch teachers use this practice in action; and download activity ideas to try in your classroom.',
        imgSrc: "/static/images/topics/thumbnail-celebrate-mistakes.png",
        imgAlt: "Celebrate Mistakes",
      },
      {
        link: '/topics/assessments-growth-mindset-math',
        title: 'Assessments for a Growth Mindset',
        description: 'Learn about assessments that promote a growth mindset from Jo Boaler.',
        imgSrc: "/static/images/topics/thumbnail-assessments-growth-mindset-math.png",
        imgAlt: "Assessments for a Growth Mindset",
      },
      {
        link: '/topics/give-tasks-promote-struggle-growth',
        title: 'Math - Give Tasks That Promote Struggle and Growth',
        description: 'Learn from Jo Boaler about how opening up a math task can promote a focus on growth, and see how to turn closed math tasks into open tasks.',
        imgSrc: "/static/images/topics/thumbnail-give-tasks-promote-struggle-growth.png",
        imgAlt: "Give Tasts That Promote Struggle and Growth",
      }
    ];
    $scope.topics.belonging = [
      {
        link: '/belonging',
        title: 'Belonging for Educators',
        description: 'When students feel like they belong in school, they are more motivated, engaged, and ultimately show higher performance. In this course, you will learn about belonging, why it’s important, and belonging strategies for your classroom.',
        imgSrc: '/static/images/topics/thumbnail-belonging.png',
        imgAlt: "Belonging for Educators"
      }
    ];

    $scope.topics.specialized = [
      {
        link: "/growth-mindset-parents",
        title: 'Growth Mindset for Parents',
        description: 'Developed in collaboration with Raise The Bar. Parents learn what a growth mindset is, why it’s important, and best practices to support their children in developing this learning belief.',
        imgSrc: "/static/images/topics/thumbnail-growth-mindset-parents.png",
        imgAlt: "Growth Mindset for Parents",
      },
      {
        link: "/growth-mindset-mentors",
        title: 'Growth Mindset for Mentors',
        description: 'Developed in collaboration with MENTOR. Mentors can be powerful teachers and reinforcers of growth mindset principles and approaches in the youth they serve. This toolkit can help mentors understand growth mindset and how to apply growth mindset strategies to many of the challenges that youth and adults face in life.',
        imgSrc: "/static/images/topics/thumbnail-growth-mindset-mentors.png",
        imgAlt: "Growth Mindset for Mentors",
      },
      {
        link: "/growth-mindset-educator-teams",
        title: 'Growth Mindset for Educator Teams',
        description: 'Teachers who have opportunities for sustained, ongoing professional development that is linked to classroom practices are more likely to see meaningful changes in their practices.',
        imgSrc: "/static/images/topics/thumbnail-growth-mindset-educator-teams.png",
        imgAlt: "Growth Mindset for Educator Teams",
      }
    ];

    var allTopics = $scope.topics.gmsForEducators.concat(
      $scope.topics.belonging,
      $scope.topics.specialized
    );

    $scope.highlightedTopic = allTopics[Math.floor(Math.random() * allTopics.length)];

	}]);
