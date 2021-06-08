#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May 11 20:08:58 2020

@author: maheshpandit
"""

import pandas as pd
from gurobipy import Model, GRB

def optimize( occupency, course_info, preferences, rooms, output ):
    ''' This function is used to optimize the scheduling of classes in phase two 
        The input files are:
        - occupency: This file icludes the information about when classrooms are available/occupied
        - course_info: This file includes information about courses for different programs that need to be scheduled
        - preferences: This file includes the preferences of students to attend different classes in morning/evening/afternoon
        - rooms: This file includes the list of all the rooms and the number of seats in each room
    '''
    
    # Read input files
    occupency = pd.read_csv(occupency, index_col = 0)
    occupency = occupency.fillna(0)
    course_info = pd.read_csv(course_info)
    preferences = pd.read_csv(preferences)
    rooms = pd.read_csv(rooms, index_col = 0)

    I = occupency.columns.values[1:]     # List of all rooms
    J = course_info.course.values        # List of all courses
    S = course_info.program.unique()     # List of all programs
    
    # List M consists of all early morning time slots
    M = ['M8.0', 'M8.5', 'M9.0', 'M9.5', 'T8.0', 'T8.5', 'T9.0', 'T9.5', 'W8.0', 'W8.5', 'W9.0', 'W9.5', 'Th8.0', 'Th8.5', 'Th9.0', 'Th9.5', 'F8.0', 'F8.5', 'F9.0', 'F9.5']
    # List E consists of all late eveing time slots
    E = ['M20.0', 'M20.5', 'M21.0', 'M21.5', 'T20.0', 'T20.5', 'T21.0', 'T21.5', 'W20.0', 'W20.5', 'W21.0', 'W21.5', 'Th20.0', 'Th20.5', 'Th21.0', 'Th21.5', 'F20.0', 'F20.5', 'F21.0', 'F21.5']
    
    A = [] # List of all 1.5 hour slots
    B = [] # List of all 2 hour slots
    C = [] # List of all 3 hour slots
    
    # Add a slot to list A if the next two slots in a room are available
    for i in occupency.index[:-2]:
        for j in occupency.columns.values[1:]:
            if (occupency.loc[i, j] == 0 and occupency.loc[i+1, j] == 0 and occupency.loc[i+2, j] == 0):
                A.append('A_'+j+'_'+str(i))
                
    # Add a slot to list B if the next three slots in a room are available
    for i in occupency.index[:-3]:
        for j in occupency.columns.values[1:]:
            if (occupency.loc[i, j] == 0 and occupency.loc[i+1, j] == 0 and occupency.loc[i+2, j] == 0 and occupency.loc[i+3, j] == 0):
                B.append('B_'+j+'_'+str(i))
                
    # Add a slot to list C if the next five slots in a room are available
    for i in occupency.index[:-5]:
        for j in occupency.columns.values[1:]:
            if (occupency.loc[i, j] == 0 and occupency.loc[i+1, j] == 0 and occupency.loc[i+2, j] == 0 and occupency.loc[i+3, j] == 0 and occupency.loc[i+4, j] == 0 and occupency.loc[i+5, j] == 0):
                C.append('C_'+j+'_'+str(i))

    Z = A + B + C
    
    prefs = assignPreferences( preferences, occupency, M, E ) #obtain prefeernc scores for eeach slot
    
    mod = Model()
    X = mod.addVars( I, J, Z, vtype = GRB.BINARY) # Binary decision variables: whether course j should be schedulde in room i at time z
    
    max_morn = mod.addVar() # Maximum number of early morning classes
    min_morn = mod.addVar() # Minimum number of early morning classes
    max_evn = mod.addVar()  # Maximum number of late evening classes
    min_evn = mod.addVar()  # Minimum number of late evening classes
    
    # The sum of preference scores for scheduled classes
    preference_score = sum( X[i, j, z] * prefs.loc[(prefs.course == j) & (prefs.time_slot == int(z.split('_')[-1]))].pref.item() for i in I for j in J for z in Z )

    # Thee sum of the number of empty seats in each scheduled class
    empty_seats = sum( X[i, j, z] * (rooms.loc[i, 'Size'] - course_info.loc[course_info.course == j].pred_reg_count.values[0]) for i in I for j in J for z in Z)

    morn_diff = max_morn - min_morn
    evn_diff = max_evn - min_evn
    
    mod.setObjective( preference_score - empty_seats - morn_diff - evn_diff, sense = GRB.MAXIMIZE )
    
    # The number of hours scheduled for each course must be equal to the number of hours required
    for j in J:
        mod.addConstr( sum( X[i, j, z]*1.5 for i in I for z in A ) + sum( X[i, j, z]*2 for i in I for z in B ) + sum( X[i, j, z]*3 for i in I for z in C ) == course_info.loc[course_info.course==j].hours_per_week.item() )
    
    # If a session of type C is scheduled, the next 5 sessions in the same room cannot be taken
    for i in C:
        overlapping_sessions = []
        session_num = int(i.split('_')[-1])
        room = i.split('_')[1]
        overlap = range(session_num, session_num+6)
        for s in overlap:
            if 'C_'+room+'_'+str(s) in C:
                overlapping_sessions.append( 'C_'+room+'_'+str(s) )
            if 'A_'+room+'_'+str(s) in A:
                overlapping_sessions.append( 'A_'+room+'_'+str(s) )
            if 'B_'+room+'_'+str(s) in B:
                overlapping_sessions.append( 'B_'+room+'_'+str(s) )
        mod.addConstr( sum( X[i, j, z] for i in I for j in J for z in overlapping_sessions ) <= 1 )
        
    # If a session of type B is scheduled, the next 3 sessions in the same room cannot be taken
    for i in B:
        overlapping_sessions = []
        session_num = int(i.split('_')[-1])
        room = i.split('_')[1]
        overlap = range(session_num, session_num+4)
        for s in overlap:
            if 'C_'+room+'_'+str(s) in C:
                overlapping_sessions.append( 'C_'+room+'_'+str(s) )
            if 'A_'+room+'_'+str(s) in A:
                overlapping_sessions.append( 'A_'+room+'_'+str(s) )
            if 'B_'+room+'_'+str(s) in B:
                overlapping_sessions.append( 'B_'+room+'_'+str(s) )
        mod.addConstr( sum( X[i, j, z] for i in I for j in J for z in overlapping_sessions ) <= 1 )
        
    # If a session of type A is scheduled, the next 2 sessions in the same room cannot be taken
    for i in A:
        overlapping_sessions = []
        session_num = int(i.split('_')[-1])
        room = i.split('_')[1]
        overlap = range(session_num, session_num+3)
        for s in overlap:
            if 'C_'+room+'_'+str(s) in C:
                overlapping_sessions.append( 'C_'+room+'_'+str(s) )
            if 'A_'+room+'_'+str(s) in A:
                overlapping_sessions.append( 'A_'+room+'_'+str(s) )
            if 'B_'+room+'_'+str(s) in B:
                overlapping_sessions.append( 'B_'+room+'_'+str(s) )
        mod.addConstr( sum( X[i, j, z] for i in I for j in J for z in overlapping_sessions ) <= 1 )
        
    # The number of seats in a room must be equal to or grater than the numbeer of seats offerred in the course
    for i in I:
        for j in J:
            for z in Z:
                mod.addConstr( rooms.loc[i, 'Size'] - ( course_info.loc[course_info.course == j].pred_reg_count.item() * X[i, j, z] ) >= 0 )
                
    morning_codes = getMorningCodes( M, I, occupency, A, B, C ) # Codes of all early morning sessions
    evening_codes = getEveningCodes( E, I, occupency, A, B, C ) # Codes of all early morning sessions
    
    # The minium/maximum number of early morning/late evening classes among all programs
    for s in S:
        courses = course_info.loc[course_info.program == s].course.unique()
        mod.addConstr( sum(X[i, j, z] for i in I for j in courses for z in morning_codes ) <= max_morn )
        mod.addConstr( sum(X[i, j, z] for i in I for j in courses for z in morning_codes ) >= min_morn )
        mod.addConstr( sum(X[i, j, z] for i in I for j in courses for z in evening_codes ) <= max_evn )
        mod.addConstr( sum(X[i, j, z] for i in I for j in courses for z in evening_codes ) >= min_evn )
        
    # Classes can only be scheduled in the rooms when the room name in the session ID is the same    
    for i in I:
        for j in J:
            for z in Z:
                if i != z.split('_')[1]:  #Check if the room is same as room name in session ID
                    mod.addConstr( X[i, j, z] == 0 )
                    
    # No overlapping core courses for any program                
    for s in S:
        core_courses = course_info.loc[(course_info.program == s) & (course_info.core ==1)].course.values
        for z in Z:
            
            # If the core course starts in a slot of type 'A', there cannot be any other core courses during the next 2 sessions
            if z.split('_')[0] == 'A':
                overlap_sessions = range( int(z.split('_')[-1]), int(z.split('_')[-1]) + 3 )
                overlap_codes = [ 'A_'+ z.split('_')[1] + '_' + str(session) for session in overlap_sessions ]
                restricted_codes = []
                for code in overlap_codes:
                    if code in A:
                        restricted_codes.append( code )
                mod.addConstr( sum( X[i, j, k] for i in I for j in core_courses for k in restricted_codes ) <= 1 )
                
                
            # If the core course starts in a slot of type 'B', there cannot be any other core courses during the next 3 sessions
            if z.split('_')[0] == 'B':
                overlap_sessions = range( int(z.split('_')[-1]), int(z.split('_')[-1]) + 4 )
                overlap_codes = [ 'B_'+ z.split('_')[1] + '_' + str(session) for session in overlap_sessions ]
                restricted_codes = []
                for code in overlap_codes:
                    if code in B:
                        restricted_codes.append( code )
                mod.addConstr( sum( X[i, j, k] for i in I for j in core_courses for k in restricted_codes ) <= 1 )

            # If the core course starts in a slot of type 'C', there cannot be any other core courses during the next 5 sessions    
            if z.split('_')[0] == 'C':
                overlap_sessions = range( int(z.split('_')[-1]), int(z.split('_')[-1]) + 6 )
                overlap_codes = [ 'C_'+ z.split('_')[1] + '_' + str(session) for session in overlap_sessions ]
                restricted_codes = []
                for code in overlap_codes:
                    if code in C:
                        restricted_codes.append( code )
                mod.addConstr( sum( X[i, j, k] for i in I for j in core_courses for k in restricted_codes ) <= 1 )
                
        mod.optimize()
        
        # Write the output in a csv file
        for i in I:
            for j in J:
                for z in Z:
                    if X[i, j, z].x:
                        session_type = z.split('_')[0]
                        session_number = int(z.split('_')[-1])
                        occupency.loc[ session_number, i ] = j
                        occupency.loc[ session_number + 1, i ] = j
                        occupency.loc[ session_number + 2, i ] = j
                        if session_type == 'B' or session_type == 'C':
                            occupency.loc[ session_number + 3, i ] = j
                        if session_type == 'C':
                            occupency.loc[ session_number + 4, i ] = j
                            occupency.loc[ session_number + 5, i ] = j


        occupency.to_csv(output)
        
        print('*'*30 + '\n Optimization Completed \n' + '*'*30)
    

def assignPreferences( preferences, occupency, M, E ):
    ''' This function assigns a prefrence scoree to each available time slot
        based on the students' preferences for each class in the morning/afternoon/evening
        M is the list of all morning slots
        E is the list of all evening slots
    '''
    
    t = []
    for i in preferences.course_code.unique():
        for m in M:
            val = preferences.loc[(preferences['course_code'] == i) & (preferences['time'] == 'Morning'), 'avg_pref'].values[0]
            session = occupency.loc[occupency['Time'] == m].index[0]
            t.append([i, session, val])
        for e in E:
            val = preferences.loc[(preferences['course_code'] == i) & (preferences['time'] == 'Evening'), 'avg_pref'].values[0]
            session = occupency.loc[occupency['Time'] == e].index[0]
            t.append([i, session, val])
        for a in occupency.Time.values:
            if a not in M+E:
                session = occupency.loc[occupency['Time'] == a].index[0]
                val = preferences.loc[(preferences['course_code'] == i) & (preferences['time'] == 'Afternoon'), 'avg_pref'].values[0]
                t.append([i, session, val])

    prefs = pd.DataFrame(t)
    prefs.columns = ['course', 'time_slot', 'pref']
    return prefs




def getMorningCodes( M, I, occupency, A, B, C ):
    ''' Get the codes for all morning sessions in different rooms, corresponding to the list M '''
    
    morning_codes = []
    for m in M:
        for i in I:
            A_code = 'A_'+i+'_'+str(occupency.loc[occupency.Time == m].index.values[0])
            if A_code in A:
                morning_codes.append(A_code)
            B_code = 'B_'+i+'_'+str(occupency.loc[occupency.Time == m].index.values[0])
            if B_code in B:
                morning_codes.append(B_code)
            C_code = 'C_'+i+'_'+str(occupency.loc[occupency.Time == m].index.values[0])
            if C_code in C:
                morning_codes.append(C_code)
    return morning_codes



def getEveningCodes( E, I, occupency, A, B, C ):
    ''' Get the codes for all evening sessions in different rooms, corresponding to the list E '''
    
    evening_codes = []
    for m in E:
        for i in I:
            A_code = 'A_'+i+'_'+str(occupency.loc[occupency.Time == m].index.values[0])
            if A_code in A:
                evening_codes.append(A_code)
            B_code = 'B_'+i+'_'+str(occupency.loc[occupency.Time == m].index.values[0])
            if B_code in B:
                evening_codes.append(B_code)
            C_code = 'C_'+i+'_'+str(occupency.loc[occupency.Time == m].index.values[0])
            if C_code in C:
                evening_codes.append(C_code)
    return evening_codes

if __name__=='__main__':
    import sys
    print (f'Running {sys.argv[0]} using argument list {sys.argv}')
    optimize( sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] )
    