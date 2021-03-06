'''
    AuthUsers se encarga de gestionar la autenticacion de usuarios.
    @author: Robin
    @since: 28-02-2018
    @summary: Clase para la gestion de usuarios del sistema
'''
'''
    Declaracion de variables globales.
    @keyword lcn_cnctn: esta variable contiene la conexion a la bd.
'''
import hashlib, socket, json,random  # @UnresolvedImport
from urllib.parse import urlparse

from IPy import IP
from flask import make_response  # @UnresolvedImpor
from flask_restful import request, Resource
import jwt  # @UnresolvedImport
from wtforms import Form, validators, StringField

from Static.ConnectDB import ConnectDB  # @UnresolvedImport
from Static.Ldap_connect import Conexion_ldap  # @UnresolvedImport
from Static.Utils import Utils  # @UnresolvedImport
import Static.config as conf  # @UnresolvedImport
import Static.config_DB as dbConf  # @UnresolvedImport
import Static.errors as errors  # @UnresolvedImport
import Static.labels as labels  # @UnresolvedImport
from ValidacionSeguridad import ValidacionSeguridad  # @UnresolvedImport

lc_cnctn = ConnectDB()
Utils = Utils()
validacionSeguridad = ValidacionSeguridad()

'''
    @since: 28-02-2018
    @summary: para la validacion de datos provenientes del POST en el login
'''


class UsuarioAcceso(Form):
    username = StringField(labels.lbl_nmbr_usrs, [validators.DataRequired(message=errors.ERR_NO_INGSA_USRO)])
    password = StringField(labels.lbl_cntrsna_usrs, [validators.DataRequired(message=errors.ERR_NO_INGRSA_CNTRSNA)])


'''
    UsroCmbioCntrsna
    @author: Robin
    @since: 28-02-2018
    @summary: Clase para la validacion de datos del POST en el cambio de contrasenna
'''


class UsroCmbioCntrsna(Form):
    cntrsna = StringField(labels.lbl_cntrsna_usrs, [validators.DataRequired(message=errors.ERR_NO_INGRSA_CNTRSNA)])
    cntrsna_nva = StringField(labels.lbl_nva_cntrsna, [validators.DataRequired(message=errors.ERR_NO_DB_INGRSR_NVA_CNTRSNA), validators.Length(min=conf.PW_MN_SIZE, message=errors.ERR_NO_MNM_CRCTRS), validators.Regexp('(?=.*\d)', message=errors.ERR_NO_MNMO_NMRO), validators.Regexp('(?=.*[A-Z])', message=errors.ERR_NO_MNMO_MYSCLA)])
    tkn = StringField('el token', [validators.DataRequired(message='Falta el token'), validators.Length(min=conf.SS_TKN_SIZE, message=errors.ERR_NO_TKN_INVLDO)])


'''
    UsroCmbioCntrsna
    @author: Robin
    @since: 28-02-2018
    @summary: Clase de autenticacion recibe la solicitud  del metodo a ejecutar:
'''


class AutenticacionUsuarios(Resource):

    '''
        @author: Robin
        @since: 28-02-2018
        @summary: Metodo para la recepcion de petisiones via POST:
        @param **kwargs: recibe
        @return: redireciona al metodo correspondiente da la paticion.
    '''

    def post(self, **kwargs):
        if kwargs['page'] == 'login':
            return self.login()
        elif kwargs['page'] == 'menu':
            return self.MenuDefectoUsuario()
        elif kwargs['page'] == 'cambio_password':
            return self.CmboCntrsna()
        elif kwargs['page'] == 'imagen_usuario':
            return self.BusquedaImagenUsuario()
        elif kwargs['page'] == 'logout':
            return self.logout()

    '''
        @author: Robin
        @since: 28-02-2018
        @summary: Metodo para la recepcion de petisiones via POST:
        @param **kwargs: recibe
        @return: redireciona al metodo correspondiente da la paticion.
    '''

    def login(self):
        ingreso = False
        error = None
        u = UsuarioAcceso(request.form)

        if not u.validate():
            return Utils.nice_json({labels.lbl_stts_error:u.errors}, 400)
        IpUsuario = IP(socket.gethostbyname(socket.gethostname()))
        if IpUsuario.iptype() == 'PUBLIC':
            md5 = hashlib.md5(request.form['password'].encode('utf-8')).hexdigest()
            Cursor = lc_cnctn.querySelect(dbConf.DB_SHMA + '.tblogins', 'lgn,cntrsna', "lgn='" + request.form['username'] + "' and  cntrsna='" + md5 + "'")
            if Cursor :
                if type(validacionSeguridad.validaUsuario(request.form['username'])) is dict:
                    ingreso = True
                else:
                    print("entro en sino")
                    error =  str(validacionSeguridad.validaUsuario(request.form['username']))
            else:
                ingreso
        elif IpUsuario.iptype() == 'PRIVATE':
            Cldap = Conexion_ldap()
            VerificaConexion = Cldap.Conexion_ldap(request.form['username'], request.form['password'])
            if VerificaConexion :
                if type(validacionSeguridad.validaUsuario(request.form['username'])) is dict:
                    ingreso = True
                else:
                    error = str(validacionSeguridad.validaUsuario(request.form['username']))
            else:
                ingreso

        if  ingreso:

            tmpData = validacionSeguridad.ObtenerDatosUsuario(request.form['username'])[0]
            tmpData["id_scrsl"] = validacionSeguridad.validaUsuario(request.form['username'])["id_scrsl"]
            data = json.loads(json.dumps(tmpData, indent=2))

            _cookie_data = json.dumps(tmpData, sort_keys=True, indent=4)

            #Creacion del key almacenar basado en el id_lgn_ge + random

            key = str(tmpData["id_lgn_ge"])+str(random.randint(1, 100000))
            key = hashlib.md5(key.encode('utf-8')).hexdigest()

            token = jwt.encode(data, conf.SS_TKN_SCRET_KEY+str(key), algorithm=conf.ENCRYPT_ALGORITHM).decode('utf-8')

            arrayValues = {}
            device = Utils.DetectarDispositivo(request.headers.get('User-Agent'))
            arrayValues['key'] = key
            arrayValues['token'] = str(token)
            arrayValues['ip'] = str(IpUsuario)
            arrayValues['dspstvo_accso'] = str(device)
            arrayValues['id_lgn_ge'] = str(data['id_lgn_ge'])
            if self.InsertGestionAcceso(arrayValues) :
                response = make_response('{"access_token":"' + key + '","cookie_higia":' + str(_cookie_data) + '}', 200)
            else:
                response = make_response('{"'+ labels.lbl_stts_error+'":"' + errors.ERR_TOKEN_ACTIVO+ '"}', 400)

                response.headers['Content-type'] = "application/json"
                response.headers['charset'] = "utf-8"
                response.headers["Access-Control-Allow-Origin"] = "*"
            return response
        else:
            #insertar los intentos fallidos.
            if(error is not None) :
                return Utils.nice_json({labels.lbl_stts_error:error}, 400)
            return Utils.nice_json({labels.lbl_stts_error:errors.ERR_NO_USRO_CNTSN_INVLD}, 400)

    def MenuDefectoUsuario(self):
        key = request.headers['Authorization']

        if key:
            validacionSeguridad.ValidacionToken(key)
            if validacionSeguridad :
                token =lc_cnctn.querySelect(dbConf.DB_SHMA+'.tbgestion_accesos', "token", "key='"+key+"' and estdo is true")[0]
                DatosUsuario = jwt.decode(token["token"], conf.SS_TKN_SCRET_KEY+key, 'utf-8')
                id_lgn_prfl_scrsl = validacionSeguridad.validaUsuario(DatosUsuario['lgn'])

                if type(id_lgn_prfl_scrsl) is not dict:
                    return id_lgn_prfl_scrsl

                strQuery = 'SELECT a."text",a.id_lgn_prfl_scrsl,a.id,a.id_mnu_ge,a.parentid,a.lnk as enlace,'\
                            '(case when d.id is null then false else d.estdo end) as favorito, '\
                            '(case when (select k.id from( '\
                            'select p.id from '+dbConf.DB_SHMA+'.tbpermisos_perfiles_menu as ppm '\
                            'left join '+dbConf.DB_SHMA+'.tbpermisos p on p.id=ppm.id_prmso '\
                            'where p.id=5 and ppm.id_prfl_une_mnu = pum.id and ppm.estdo=true '\
                            ') as k) is null then false else true end) as crear, '\
                            '(case when (select k.id from( '\
                            'select p.id from '+dbConf.DB_SHMA+'.tbpermisos_perfiles_menu as ppm '\
                            'left join '+dbConf.DB_SHMA+'.tbpermisos p on p.id=ppm.id_prmso  '\
                            'where p.id=6 and ppm.id_prfl_une_mnu = pum.id and ppm.estdo=true  '\
                            ') as k) is null then false else true end) as actualizar,  '\
                            '(case when (select k.id from( '\
                            'select p.id from '+dbConf.DB_SHMA+'.tbpermisos_perfiles_menu as ppm '\
                            'left join '+dbConf.DB_SHMA+'.tbpermisos p on p.id=ppm.id_prmso '\
                            'where p.id=7 and ppm.id_prfl_une_mnu = pum.id and ppm.estdo=true '\
                            ') as k) is null then false else true end) as anular, '\
                            '(case when (select k.id from( '\
                            'select p.id from '+dbConf.DB_SHMA+'.tbpermisos_perfiles_menu as ppm '\
                            'left join '+dbConf.DB_SHMA+'.tbpermisos p on p.id=ppm.id_prmso '\
                            'where p.id=8 and ppm.id_prfl_une_mnu = pum.id and ppm.estdo=true '\
                            ') as k)is null then false else true end) as imprimir, '\
                            '(case when (select k.id from( '\
                            'select p.id from '+dbConf.DB_SHMA+'.tbpermisos_perfiles_menu as ppm '\
                            'left join '+dbConf.DB_SHMA+'.tbpermisos p on p.id=ppm.id_prmso '\
                            'where p.id=9 and ppm.id_prfl_une_mnu = pum.id and ppm.estdo=true '\
                            ') as k)is null then false else true end) as exportar '\
                            'FROM (select '\
                            'c.dscrpcn as text , a.id_lgn_prfl_scrsl, b.id_mnu as id ,a.id_mnu_ge, c.id_mnu as parentid , c.lnk ,a.id Mid,c.ordn  '\
                            'FROM '+dbConf.DB_SHMA+'.tblogins_perfiles_menu as a  '\
                            'INNER JOIN '+dbConf.DB_SHMA+'.tbmenu_ge b on a.id_mnu_ge=b.id  '\
                            'INNER JOIN '+dbConf.DB_SHMA+'.tbmenu as c ON b.id_mnu = c.id where a.estdo=true  and b.estdo=true  '\
                            'and a.id_lgn_prfl_scrsl = ' + str(id_lgn_prfl_scrsl['id_prfl_scrsl']) + '  ) as a '\
                            'LEFT JOIN '+dbConf.DB_SHMA+'.tbfavoritosmenu as d on d.id_lgn_prfl_mnu = a.Mid  '\
                            'LEFT JOIN '+dbConf.DB_SHMA+'.tblogins_perfiles_sucursales as lps on lps.id = a.id_lgn_prfl_scrsl '\
                            'LEFT JOIN '+dbConf.DB_SHMA+'.tbperfiles_une_menu pum on pum.id_prfl_une = lps.id_prfl_une and pum.id_mnu_ge = a.id_mnu_ge '\
                            'ORDER BY  cast(a.ordn as integer)'

                Cursor = lc_cnctn.queryFree(strQuery)
                if Cursor :
                    data = json.loads(json.dumps(Cursor, indent=2))
                    return Utils.nice_json(data, 200)
                else:
                    return Utils.nice_json({labels.lbl_stts_error:errors.ERR_NO_USRO_SN_MNU}, 400)
            else:
                return Utils.nice_json({labels.lbl_stts_error:errors.ERR_NO_SN_SSN}, 400)

        else:
            return Utils.nice_json({labels.lbl_stts_error:errors.ERR_NO_SN_PRMTRS}, 400)

    def CmboCntrsna(self):
        u = UsroCmbioCntrsna(request.form)
        if not u.validate():
            return Utils.nice_json({"status":"Error", "error":u.errors, "user":"null"}, 200)

    def BusquedaImagenUsuario(self):
        lc_url = request.url
        lc_prtcl = urlparse(lc_url)
        Cursor = lc_cnctn.queryFree(" select "\
                                 " id ,"\
                                 " lgn ,"\
                                 " fto_usro,"\
                                 " nmbre_usro, "\
                                 " estdo "\
                                 " from " + dbConf.DB_SHMA + ".tblogins where lgn = '" + str(request.form['username']) + "'")
        if Cursor :
            data = json.loads(json.dumps(Cursor[0], indent=2))
            if data['estdo']:
                if data['fto_usro']:
                    return Utils.nice_json({"fto_usro":lc_prtcl.scheme + '://' + conf.SV_HOST + ':' + str(conf.SV_PORT) + '/static/img/' + data['fto_usro']}, 200)
                else:
                    return Utils.nice_json({"fto_usro":"null"}, 200)
            else:
                return Utils.nice_json({labels.lbl_stts_error:errors.ERR_NO_TNE_PRFL, lc_prtcl.scheme + '://' + "fto_usro":conf.SV_HOST + ':' + str(conf.SV_PORT) + '/static/img/' + data['fto_usro']}, 200)
        else:
            return Utils.nice_json({labels.lbl_stts_error:errors.ERR_NO_TNE_PRMTDO_ACCDR}, 400)

    def InsertGestionAcceso(self, objectValues):
        #Verifica si el usuario tiene una session abierta sino la tiene la inserta
        Cursor = lc_cnctn.querySelect(dbConf.DB_SHMA + ".tbgestion_accesos","id","id_lgn_ge="+objectValues["id_lgn_ge"] +" AND estdo = true" )
        if not Cursor:
            lc_cnctn.queryInsert(dbConf.DB_SHMA + ".tbgestion_accesos", objectValues)
            return True
        else:
            return False

    '''
        @author: Robin
        @since: 01-03-2018
        @summary: Metodo para invalidar el token:
        @param reques: recibe form
        @return: object error or success.
    '''
    def logout(self):
        key = request.headers['Authorization']
        validacionSeguridad.ValidacionToken(key)
        if validacionSeguridad :
            token =lc_cnctn.querySelect(dbConf.DB_SHMA+'.tbgestion_accesos', "token", "key='"+key+"'")[0]
            DatosUsuario = jwt.decode(token["token"], conf.SS_TKN_SCRET_KEY+key, 'utf-8')
            lc_updte ="UPDATE SSI7X.tbgestion_accesos SET estdo=false,fcha_mdfcn = now()," \
            "tmpo_actvdd = (now()::timestamp - fcha_mdfcn::timestamp)::varchar(8) WHERE id_lgn_ge = "+str(DatosUsuario["id_lgn_ge"]) +" AND estdo=true"


            lb_resultado = lc_cnctn.queryUpdateFree(lc_updte)

            if lb_resultado:
                return Utils.nice_json({labels.lbl_stts_success:"BYE"}, 200)
            else:
                return Utils.nice_json({labels.lbl_stts_error:errors.ERR_NO_LOGOUT} , 400)
