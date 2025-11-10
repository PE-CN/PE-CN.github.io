{% extends '_layout.swig' %}
{% import '_macro/sidebar.swig' as sidebar_template with context %}

{% block title %}{{ title }}{%- if theme.index_with_subtitle and subtitle %} - {{ subtitle }}{%- endif %}{% endblock %}

{% block class %}index posts-expand{% endblock %}

{% block content %}


<h2 style="font-family:Arial,helvetic,sans-serif;">About Project Euler</h2>
<img src="images/avatar.png" alt="Leonhard Euler (1707-1783)" style="margin:10px;float:right;">
<h2>关于欧拉计划</h2>
<h3 style="font-family:'Courier New',monospace;">What is Project Euler?</h3>
<h3>什么是欧拉计划？</h3>
<p style="font-family:Verdana, Lato, 'Microsoft YaHei Light', sans-serif;">Project Euler is a series of challenging mathematical/computer programming problems that will require more than just mathematical insights to solve. Although mathematics will help you arrive at elegant and efficient methods, the use of a computer and programming skills will be required to solve most problems.<br>
欧拉计划是一系列有挑战性的数学与计算机编程题；要解开它们，需要的不止是数学知识：尽管数学能够帮助你找到一些优雅而有效的方法，大多数题目仍需要借助计算机和编程技巧来完成解答。<br><br>
The motivation for starting Project Euler, and its continuation, is to provide a platform for the inquiring mind to delve into unfamiliar areas and learn new concepts in a fun and recreational context.<br>
创立欧拉计划的初衷，以及不断维持其运行的动力，在于为好奇的头脑提供一个平台，使他们能够在有趣愉悦的氛围中，探索未知领域，学习新的知识。
</p>
<br>
<h3 style="font-family:'Courier New',monospace;">Who are the problems aimed at?</h3>
<h3>这些题目的受众是谁？</h3>
<p style="font-family:Verdana, Lato, 'Microsoft YaHei Light', sans-serif;">The intended audience include students for whom the basic curriculum is not feeding their hunger to learn, adults whose background was not primarily mathematics but had an interest in things mathematical, and professionals who want to keep their problem solving and mathematics on the cutting edge.<br>
欧拉计划预期的受众，包括在基础课程外学有余力的学生、非数学背景但对数学感兴趣的成年人以及希望磨炼解题能力或是数学能力的专业人士。</p>
<br>
<h3 style="font-family:'Courier New',monospace;">Can anyone solve the problems?</h3>
<h3>所有人都能解开这些题目吗？</h3>
<p style="font-family:Verdana, Lato, 'Microsoft YaHei Light', sans-serif;">The problems range in difficulty and for many the experience is inductive chain learning. That is, by solving one problem it will expose you to a new concept that allows you to undertake a previously inaccessible problem. So the determined participant will slowly but surely work his/her way through every problem.<br>
欧拉计划的题目难度不一，对于大多数人来说，解题就是一个逐渐学习的过程。也就是说，每当你解开一个题目，你将会了解一些新的知识，从而帮助你着手解决以前无从下手的题目。因此，任何有决心的参与者，即使进展再缓慢，也一定能逐一解开每一道题。
</p>
<br>
<h3 style="font-family:'Courier New',monospace;">What next?</h3>
<h3>下一步做什么？</h3>
<p style="font-family:Verdana, Lato, 'Microsoft YaHei Light', sans-serif;">In order to track your progress it is necessary to setup an account and have Cookies enabled. If you already have an account then <a href="https://projecteuler.net/sign_in">Login</a>, otherwise please <a href="https://projecteuler.net/register">Register</a> – it's completely free!<br>为了记录你的解题进展，你需要注册一个账户，并保证你的浏览器启用Cookies。如果你已经拥有账户，请<a href="https://projecteuler.net/sign_in">登录</a>，否则请<a href="https://projecteuler.net/register">注册</a>——这是完全免费的！</p>
<p style="font-family:Verdana, Lato, 'Microsoft YaHei Light', sans-serif;">However, as the problems are challenging then you may wish to view the <a href="https://projecteuler.net/problems">Problems</a> before registering.<br>不过，由于题目具有挑战性，你也许应该先了解一下<a href="http://PE-CN.github.io/problems">题目</a>再开始注册。</p>
<blockquote class="blockquote-center"><span style="font-style:italic; font-family:'Trebuchet MS',Verdana,Lato,sans-serif;">"Project Euler exists to encourage, challenge, and develop the skills and enjoyment of anyone with an interest in the fascinating world of mathematics."</span><br>
<span style="font-family:STKaiti,Kaiti,Kai,serif;font-size:110%;">“欧拉计划的存在，是为了每个对数学感兴趣的人，鼓励他们，挑战他们，并最终培养他们的能力与乐趣。”</span>
</blockquote>

{% endblock %}

{% block sidebar %}
  {{ sidebar_template.render(false) }}
{% endblock %}
