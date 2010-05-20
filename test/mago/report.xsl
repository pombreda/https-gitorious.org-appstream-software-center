<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:template match="/">
    <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en" dir="ltr">
      <head>
        <title>
    Mago Tests Report
</title>
<style>

body
{
	line-height: 1.6em;
    margin: 45px;
  	font-family: "Lucida Sans Unicode", "Lucida Grande", Sans-Serif;
	font-size: 12px;
}
p
{

}

h4
{
line-height: 20%;
color: #039;
}

h1
{
line-height: 20%;
color: #34679D;
}

#mago-table
{
	font-family: "Lucida Sans Unicode", "Lucida Grande", Sans-Serif;
	font-size: 12px;
	margin: 45px;
	text-align: left;
	border-collapse: collapse;
}
#mago-table th
{
	font-size: 13px;
	font-weight: normal;
	padding: 8px;
	background: #B3B3E6;
	border-bottom: 5px solid #fff;
	color: #039;
}
#mago-table td
{
	padding: 8px;
	background: #eef; 
	border-bottom: 1px solid #fff;
	color: #669;
	border-top: 1px solid transparent;
}
#mago-table tr:hover td
{
	background: #d0dafd;
	color: #339;
}

dd {
    color: #34679D;
    font-weight: bold;
    margin-left: 0;
}

dt {
    color: #666;
    margin-left: 2em;
}

td.result-pass {
    color: green !important;
}

td.result-fail {
    color: red !important;
}

td.result-error {
    color: orange !important;
}

</style>
    <script type="text/javascript">
     function ReverseDisplay(d) {
        if(document.getElementById(d).style.display == "none") { document.getElementById(d).style.display = "block"; }
        else { document.getElementById(d).style.display = "none"; }
      }
    </script>
      </head>
      <body>
          <h1>Mago Tests Report</h1>
          <p>
                  This are the results from a run of Mago Desktop Tests.
                  If you find false positives, please, report bugs against <a href="https://launchpad.net/mago/+filebug">Mago</a> project.
              </p>
		      <dl>
              <dd>Suite</dd>
			  <dt><xsl:value-of select="suite/@name" /></dt>
			  <dd>Class</dd>
			  <dt><xsl:value-of select="suite/class" /></dt>
              <dd>Description</dd>
			  <dt><xsl:value-of select="suite/description"/></dt>
			  </dl>
              <table id="mago-table">
                <thead>
                  <tr>
                    <th>TestCase Name</th>
                    <th>Description</th>  
                    <th>Method</th>
                    <th>Status</th>
                    <th>Time Elapsed (s)</th>
                    <th>Message</th>
                    <th>Screenshot</th>
                    <th>Stacktrace</th>
                  </tr>
                </thead>
                <tbody>
                    <xsl:for-each select="descendant::case">  
                      <tr>
                        <td>
                          <xsl:value-of select="@name"/>
                        </td>
                        <td>
                          <xsl:value-of select="child::description"/>
                        </td>
                        <td>
                          <xsl:value-of select="child::method"/>
                        </td>
                        <xsl:for-each select="descendant::result">  
                        <xsl:choose>
                          <xsl:when test="child::error/child::text() = 1">
                            <td class="result-error">Script Error</td>
                          </xsl:when>
                          <xsl:when test="child::pass/child::text() = 0">
                            <td class="result-fail">Test Failed</td>
                          </xsl:when>
                          <xsl:otherwise>
                            <td class="result-pass">Passed</td>
                          </xsl:otherwise>
                        </xsl:choose>
                        <td>
                            <xsl:value-of select="child::time/child::text()"/>
                        </td>
                        <td>
                            <xsl:value-of select="child::message/child::text()"/>
                        </td>
                        <td>
                            <xsl:apply-templates select="child::screenshot" mode="link"/>
                        </td>
                        <td>
                            <xsl:if test="child::pass/child::text() != 1 or child::error/child::text() = 1">
                                <xsl:call-template name="stacktemplate">
                                    <xsl:with-param name="stackid">
                                        <xsl:value-of select="translate(../@name, ' ', '_')" />
                                    </xsl:with-param>
                                    <xsl:with-param name="stacktext">
                                        <xsl:value-of select="child::stacktrace/child::text()" />
                                    </xsl:with-param>
                                </xsl:call-template>
                            </xsl:if>
                        </td>
                        </xsl:for-each>
                      </tr>
                  </xsl:for-each>
                  
                  <xsl:for-each select="suite/result">
                      <tr></tr>
                      <tr>
                          <td colspan="7"><font color="red"><h2><b>The suite had an error in the setup, teardown or cleanup methods.</b></h2></font></td>
                          <td>
                            <xsl:call-template name="stacktemplate">
                                <xsl:with-param name="stackid">
                                    <xsl:value-of select="string('testsuite_stacktrace')" />
                                </xsl:with-param>
                                <xsl:with-param name="stacktext">
                                    <xsl:value-of select="child::stacktrace/child::text()" />
                                </xsl:with-param>
                            </xsl:call-template>
                        </td>                        
                      </tr>
                  </xsl:for-each>
                </tbody>
              </table>
              <p>
                <!-- *** Last Paragraph Space *** -->
              </p>
      </body>
    </html>
  </xsl:template>
  <xsl:template match="screenshot" mode="link">
    <a href="{text()}">
      <xsl:value-of select="text()"/>
    </a>
  </xsl:template>
  <xsl:template name="stacktemplate">
      <xsl:param name="stackid" />
      <xsl:param name="stacktext" />
      <a href="javascript:ReverseDisplay('{$stackid}')">
          [Show/Hide Stacktrace]
      </a>
      <div id="{$stackid}" style="display:none;">
       <pre>
          <xsl:value-of select="$stacktext" />
      </pre>
      </div>
 </xsl:template>
</xsl:stylesheet>
